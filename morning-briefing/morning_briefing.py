#!/usr/bin/env python3
"""
MIT License

Copyright (c) 2026 OpenClaw Community

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

"""
Morning Health Briefing Data Collector

Comprehensive morning briefing system that pulls sleep, heart rate, HRV, 
calendar, weather, and activity data from Fulcra API and external sources.
Outputs structured JSON for automated briefing composition.

Key Features:
- Multi-domain health data aggregation
- Sleep stage analysis with quality assessment
- Heart rate and HRV trend analysis
- Calendar event summarization
- Weather data integration
- Cross-platform timezone handling
- Error-safe data collection

Built with OpenClaw + Fulcra for automated morning briefings.

Output: Structured JSON to stdout for briefing composition.
"""

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from fulcra_api.core import FulcraAPI

# Configurable paths and settings via environment variables
TOKEN_FILE = os.environ.get(
    "FULCRA_TOKEN_PATH",
    os.path.expanduser("~/.config/fulcra/token.json")
)

# Configurable weather locations (comma-separated)
WEATHER_LOCATIONS = os.environ.get(
    "WEATHER_LOCATIONS", 
    "New+York,Boston"  # Default locations
).split(",")

# Configurable timezone offset for local time (hours from UTC)
LOCAL_UTC_OFFSET = int(os.environ.get("LOCAL_UTC_OFFSET", "-5"))  # EST/EDT default


def load_api():
    """Load Fulcra API with saved token and expiration checking."""
    if not os.path.exists(TOKEN_FILE):
        return None, f"No token file found at {TOKEN_FILE}"
    
    try:
        with open(TOKEN_FILE, 'r') as f:
            token_data = json.load(f)
    except Exception as e:
        return None, f"Failed to read token file: {e}"
    
    # Check token expiration
    exp = token_data.get("expiration")
    if exp:
        try:
            exp_dt = datetime.fromisoformat(exp)
            if exp_dt < datetime.now(timezone.utc):
                return None, "Token expired - refresh required"
        except:
            # If expiration format is unreadable, proceed anyway
            pass
    
    api = FulcraAPI()
    api.fulcra_cached_access_token = token_data["access_token"]
    api.fulcra_cached_access_token_expiration = datetime.fromisoformat(exp) if exp else None
    return api, None


def get_sleep(api):
    """Get last night's sleep stages with quality analysis."""
    now = datetime.now(timezone.utc)
    # Look back 14 hours to capture last night's sleep
    start = (now - timedelta(hours=14)).isoformat()
    end = now.isoformat()
    
    try:
        samples = api.metric_samples(start, end, "SleepStage")
        if not samples:
            return {"available": False, "reason": "no sleep data found"}
        
        # Apple HealthKit sleep stage mapping
        stage_names = {0: "InBed", 1: "Awake", 2: "Deep", 3: "Core", 4: "REM"}
        stage_minutes = {}
        
        for s in samples:
            # Handle timezone offset formats for Python compatibility
            start_date = s['start_date']
            end_date = s['end_date']
            
            # Parse timestamps with timezone handling
            try:
                # Try modern Python datetime parsing first
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except:
                # Fallback for older Python versions
                start_dt = datetime.strptime(start_date[:19], '%Y-%m-%dT%H:%M:%S')
                end_dt = datetime.strptime(end_date[:19], '%Y-%m-%dT%H:%M:%S')
            
            # Calculate duration and accumulate by stage
            minutes = (end_dt - start_dt).total_seconds() / 60
            stage = stage_names.get(s.get('value', -1), f"Unknown({s.get('value')})")
            stage_minutes[stage] = stage_minutes.get(stage, 0) + minutes
        
        # Calculate sleep metrics
        total_time = sum(stage_minutes.values())
        sleep_minutes = sum(v for k, v in stage_minutes.items() if k not in ("InBed", "Awake"))
        
        # Sleep quality assessment
        deep_pct = stage_minutes.get("Deep", 0) / max(sleep_minutes, 1) * 100
        rem_pct = stage_minutes.get("REM", 0) / max(sleep_minutes, 1) * 100
        core_pct = stage_minutes.get("Core", 0) / max(sleep_minutes, 1) * 100
        
        # Quality classification
        quality = "good"
        if sleep_minutes < 360:  # < 6 hours
            quality = "poor"
        elif deep_pct < 10 or rem_pct < 15:
            quality = "fair"
        elif sleep_minutes >= 420 and deep_pct >= 15 and rem_pct >= 20:
            quality = "excellent"
        
        # Extract sleep timing
        try:
            first_sample = samples[0]
            last_sample = samples[-1]
            
            # Parse bedtime and wake time
            bed_dt = datetime.fromisoformat(first_sample['start_date'].replace('Z', '+00:00'))
            wake_dt = datetime.fromisoformat(last_sample['end_date'].replace('Z', '+00:00'))
            
            # Convert to local timezone for display
            local_tz = timezone(timedelta(hours=LOCAL_UTC_OFFSET))
            bed_local = bed_dt.astimezone(local_tz)
            wake_local = wake_dt.astimezone(local_tz)
            
            bed_time = bed_local.strftime("%I:%M %p")
            wake_time = wake_local.strftime("%I:%M %p")
        except:
            bed_time = wake_time = "unknown"
        
        return {
            "available": True,
            "total_hours": round(sleep_minutes / 60, 1),
            "sleep_efficiency": round(sleep_minutes / max(total_time, 1) * 100, 1),
            "stages": {k: round(v, 0) for k, v in stage_minutes.items()},
            "stage_pct": {k: round(v / max(total_time, 1) * 100, 1) for k, v in stage_minutes.items()},
            "quality": quality,
            "deep_pct": round(deep_pct, 1),
            "rem_pct": round(rem_pct, 1),
            "core_pct": round(core_pct, 1),
            "bed_time": bed_time,
            "wake_time": wake_time,
        }
        
    except Exception as e:
        return {"available": False, "reason": f"sleep analysis error: {str(e)}"}


def get_heart_rate(api):
    """Get overnight and recent heart rate data."""
    now = datetime.now(timezone.utc)
    start = (now - timedelta(hours=10)).isoformat()
    end = now.isoformat()
    
    try:
        samples = api.metric_samples(start, end, "HeartRate")
        if not samples:
            return {"available": False, "reason": "no heart rate data"}
        
        values = [s['value'] for s in samples if 'value' in s and s['value'] > 0]
        if not values:
            return {"available": False, "reason": "no valid heart rate readings"}
        
        # Calculate resting heart rate estimate (lowest 10th percentile)
        sorted_values = sorted(values)
        resting_sample_size = max(1, len(sorted_values) // 10)
        resting_estimate = sum(sorted_values[:resting_sample_size]) / resting_sample_size
        
        return {
            "available": True,
            "readings": len(values),
            "avg": round(sum(values) / len(values), 0),
            "min": round(min(values), 0),
            "max": round(max(values), 0),
            "resting_estimate": round(resting_estimate, 0),
            "time_span_hours": 10
        }
        
    except Exception as e:
        return {"available": False, "reason": f"heart rate error: {str(e)}"}


def get_hrv(api):
    """Get recent HRV (Heart Rate Variability) data."""
    now = datetime.now(timezone.utc)
    start = (now - timedelta(hours=12)).isoformat()
    end = now.isoformat()
    
    try:
        samples = api.metric_samples(start, end, "HeartRateVariabilitySDNN")
        if not samples:
            return {"available": False, "reason": "no HRV data"}
        
        values = [s['value'] for s in samples if 'value' in s and s['value'] > 0]
        if not values:
            return {"available": False, "reason": "no valid HRV readings"}
        
        return {
            "available": True,
            "readings": len(values),
            "avg_ms": round(sum(values) / len(values), 1),
            "latest_ms": round(values[-1], 1),
            "min_ms": round(min(values), 1),
            "max_ms": round(max(values), 1),
            "time_span_hours": 12
        }
        
    except Exception as e:
        return {"available": False, "reason": f"HRV error: {str(e)}"}


def get_calendar(api):
    """Get today's calendar events."""
    now = datetime.now(timezone.utc)
    # Define today's window in UTC (adjust for your timezone)
    local_midnight_utc = now.replace(hour=5, minute=0, second=0, microsecond=0)  # midnight EST = 5 AM UTC
    start = local_midnight_utc.isoformat()
    end = (local_midnight_utc + timedelta(hours=24)).isoformat()
    
    try:
        events = api.calendar_events(start, end)
        if not events:
            return {"available": True, "events": [], "count": 0}
        
        formatted_events = []
        for e in events:
            # Basic event information extraction
            event_data = {
                "title": e.get("title", "Untitled"),
                "start": e.get("start_time", ""),
                "end": e.get("end_time", ""),
                "all_day": e.get("all_day", False),
                "location": e.get("location", ""),
                "has_attendees": bool(e.get("participants")),
            }
            formatted_events.append(event_data)
        
        return {
            "available": True, 
            "events": formatted_events, 
            "count": len(formatted_events)
        }
        
    except Exception as e:
        return {"available": False, "reason": f"calendar error: {str(e)}"}


def get_weather():
    """Get weather data for configured locations using wttr.in."""
    results = {}
    
    for location in WEATHER_LOCATIONS:
        location = location.strip()
        if not location:
            continue
            
        try:
            # Use wttr.in for simple weather data
            result = subprocess.run(
                ["curl", "-s", f"wttr.in/{location}?format=%l:+%c+%t+%h+%w&m"],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0 and result.stdout.strip():
                results[location.replace("+", " ")] = result.stdout.strip()
            else:
                results[location.replace("+", " ")] = "unavailable"
                
        except Exception as e:
            results[location.replace("+", " ")] = f"error: {str(e)}"
    
    return results


def get_steps(api):
    """Get recent step count data."""
    now = datetime.now(timezone.utc)
    start = (now - timedelta(hours=24)).isoformat()
    end = now.isoformat()
    
    try:
        samples = api.metric_samples(start, end, "StepCount")
        if not samples:
            return {"available": False, "reason": "no step data"}
        
        total_steps = sum(s.get('value', 0) for s in samples)
        
        return {
            "available": True, 
            "total": round(total_steps),
            "time_span_hours": 24
        }
        
    except Exception as e:
        return {"available": False, "reason": f"steps error: {str(e)}"}


def main():
    """Main function for morning briefing data collection."""
    api, error = load_api()
    if error:
        print(json.dumps({"error": error}))
        return 1
    
    # Collect all briefing data
    briefing_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "local_timezone_offset": LOCAL_UTC_OFFSET,
        "sleep": get_sleep(api),
        "heart_rate": get_heart_rate(api),
        "hrv": get_hrv(api),
        "calendar": get_calendar(api),
        "weather": get_weather(),
        "steps": get_steps(api),
    }
    
    # Output as JSON for consumption by briefing composer
    print(json.dumps(briefing_data, indent=2, default=str))
    return 0


if __name__ == "__main__":
    exit(main())