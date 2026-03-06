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
Morning Sleep & Glucose Analysis

Generates overnight sleep fragmentation and glucose stability reports designed 
for morning briefings. Analyzes sleep quality metrics and glucose stability 
patterns from overnight data.

Key Features:
- Sleep fragmentation analysis with stage breakdown
- Overnight glucose stability assessment
- Smart data sync detection
- Morning briefing optimized output format
- Timezone-aware data windows

Built with OpenClaw + Fulcra for morning health insights.

Output: JSON with sleep and glucose overnight summaries.
"""

import json, os, sys, statistics
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

# Configurable token path via environment variable
TOKEN_PATH = os.environ.get(
    "FULCRA_TOKEN_PATH", 
    os.path.expanduser("~/.config/fulcra/token.json")
)

# Timezone configuration
LOCAL_TZ = ZoneInfo('America/New_York')  # Adjust for your timezone


def get_client():
    """Initialize Fulcra API client with configurable token path."""
    from fulcra_api.core import FulcraAPI
    client = FulcraAPI()
    
    with open(TOKEN_PATH, 'r') as f:
        td = json.load(f)
    
    client.set_cached_access_token(td['access_token'])
    client.set_cached_refresh_token(td['refresh_token'])
    return client


def get_overnight_glucose(client):
    """Get glucose readings from overnight sleep period (~10 PM to 7 AM)."""
    now = datetime.now(timezone.utc)
    
    # Define overnight window: 10 PM local yesterday to 7 AM local today
    # Convert to UTC for API calls
    end = now.replace(hour=12, minute=0, second=0, microsecond=0)  # ~7 AM local
    if now.hour < 12:
        # It's before 7 AM local — use today's window
        pass
    start = end - timedelta(hours=9)  # 9 hours = ~10 PM to 7 AM
    
    try:
        data = client.metric_samples(start.isoformat(), end.isoformat(), 'BloodGlucose')
        vals = [d.get('value', 0) for d in data if d.get('value')]
        
        if not vals:
            # Check if there's ANY recent glucose data to distinguish sync delay from sensor issues
            try:
                recent = client.metric_samples(
                    (now - timedelta(hours=48)).isoformat(), now.isoformat(), 'BloodGlucose'
                )
                if recent:
                    return {
                        "status": "no_data", 
                        "readings": 0, 
                        "summary": "⏳ CGM data not yet synced for overnight window — check back later"
                    }
            except:
                pass
            
            return {
                "status": "no_data",
                "readings": 0,
                "summary": "⚠️ No CGM data in 48h — sensor may need attention"
            }
        
        # Calculate glucose metrics
        avg = sum(vals) / len(vals)
        sd = statistics.stdev(vals) if len(vals) > 1 else 0
        glucose_range = max(vals) - min(vals)
        
        # Classify stability based on standard deviation
        if sd < 10:
            stability = "excellent"
            emoji = "🟢"
        elif sd < 20:
            stability = "good"
            emoji = "🟡"
        elif sd < 30:
            stability = "moderate"
            emoji = "🟠"
        else:
            stability = "volatile"
            emoji = "🔴"
        
        # Count concerning readings
        spikes = sum(1 for v in vals if v > 140)
        dips = sum(1 for v in vals if v < 70)
        
        summary = (f"{emoji} Overnight glucose: avg {avg:.0f} mg/dL, "
                  f"range {min(vals):.0f}–{max(vals):.0f}, "
                  f"stability {stability} (SD {sd:.1f})")
        
        return {
            "status": "ok",
            "readings": len(vals),
            "avg": round(avg, 0),
            "min": round(min(vals), 0),
            "max": round(max(vals), 0),
            "std": round(sd, 1),
            "range": round(glucose_range, 0),
            "stability": stability,
            "emoji": emoji,
            "spikes_over_140": spikes,
            "dips_under_70": dips,
            "summary": summary
        }
        
    except Exception as e:
        return {"status": "error", "error": str(e)}


def get_sleep_fragmentation(client):
    """Get last night's sleep data with detailed fragmentation analysis."""
    try:
        # Import sleep utility if available, otherwise use direct API calls
        try:
            import sys
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from fulcra_sleep_utils import get_last_night_sleep
            
            result = get_last_night_sleep(client)
            if result.get("status") != "ok":
                return result
            
            # Convert from utility format to our expected format
            return {
                "status": "ok",
                "total_sleep_hours": result["total_sleep_h"],
                "stages_minutes": result["stages"],
                "deep_pct": result["deep_pct"],
                "rem_pct": result["rem_pct"],
                "awake_minutes": result["awake_min"],
                "fragmentation_pct": result["frag_pct"],
                "fragmentation_label": result["frag_label"],
                "fragmentation_emoji": result["frag_emoji"],
                "bedtime": result["bedtime_str"],
                "efficiency": result["efficiency"],
                "sleep_start_utc": result.get("sleep_start"),
                "summary": (f"Sleep: {result['total_sleep_h']:.1f}h | "
                           f"Deep {result['deep_pct']:.0f}% | REM {result['rem_pct']:.0f}% | "
                           f"Bedtime {result['bedtime_str']} | "
                           f"{result['frag_emoji']} Fragmentation: {result['awake_min']:.0f}min awake "
                           f"({result['frag_pct']:.0f}%) — {result['frag_label']}")
            }
            
        except ImportError:
            # Fallback to direct API implementation
            return get_sleep_direct(client)
            
    except Exception as e:
        return {"status": "error", "error": str(e)}


def get_sleep_direct(client):
    """Direct sleep data fetching when utility is not available."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=2)
    
    try:
        df = client.sleep_agg(start.isoformat(), end.isoformat())
        
        if not hasattr(df, 'iterrows') or len(df) == 0:
            return {"status": "no_data"}
        
        # Process sleep data (simplified version)
        stage_names = {2: 'deep', 3: 'core', 4: 'rem', 5: 'awake'}
        stages = {}
        total_sleep_ms = 0
        awake_ms = 0
        sleep_start = None
        
        # Get most recent complete night
        target_date = (datetime.now(LOCAL_TZ).date())
        
        for _, row in df.iterrows():
            period_date = str(row.get('period_start_time', ''))[:10]
            if period_date != str(target_date):
                continue
                
            stage = int(row.get('value', 0))
            ms = float(row.get('sum_ms', 0) or 0)
            name = stage_names.get(stage, f'stage_{stage}')
            stages[name] = stages.get(name, 0) + round(ms / 60000, 1)
            
            if stage in (2, 3, 4):  # sleep stages
                total_sleep_ms += ms
                min_start = str(row.get('min_start_time', ''))
                if min_start and (not sleep_start or min_start < sleep_start):
                    sleep_start = min_start
            elif stage == 5:  # awake
                awake_ms += ms
        
        if total_sleep_ms < 1800000:  # less than 30 minutes
            return {"status": "no_data"}
        
        # Calculate metrics
        total_bed_ms = total_sleep_ms + awake_ms
        total_sleep_h = total_sleep_ms / 3600000
        awake_min = awake_ms / 60000
        frag_pct = (awake_ms / total_bed_ms * 100) if total_bed_ms > 0 else 0
        
        deep_ms = stages.get('deep', 0) * 60000
        deep_pct = (deep_ms / total_sleep_ms * 100) if total_sleep_ms > 0 else 0
        rem_ms = stages.get('rem', 0) * 60000
        rem_pct = (rem_ms / total_sleep_ms * 100) if total_sleep_ms > 0 else 0
        
        # Fragmentation classification
        if frag_pct < 10:
            frag_label, emoji = "low", "🟢"
        elif frag_pct < 20:
            frag_label, emoji = "moderate", "🟡"
        elif frag_pct < 30:
            frag_label, emoji = "high", "🟠"
        else:
            frag_label, emoji = "severe", "🔴"
        
        # Parse bedtime
        bedtime_str = ""
        if sleep_start:
            try:
                dt = datetime.fromisoformat(sleep_start.replace('Z', '+00:00'))
                dt_local = dt.astimezone(LOCAL_TZ)
                bedtime_str = dt_local.strftime('%-I:%M %p')
            except:
                pass
        
        summary = (f"Sleep: {total_sleep_h:.1f}h | Deep {deep_pct:.0f}% | REM {rem_pct:.0f}% | "
                  f"Bedtime {bedtime_str} | {emoji} Fragmentation: {awake_min:.0f}min awake "
                  f"({frag_pct:.0f}%) — {frag_label}")
        
        return {
            "status": "ok",
            "total_sleep_hours": round(total_sleep_h, 1),
            "stages_minutes": stages,
            "deep_pct": round(deep_pct, 1),
            "rem_pct": round(rem_pct, 1),
            "awake_minutes": round(awake_min, 1),
            "fragmentation_pct": round(frag_pct, 1),
            "fragmentation_label": frag_label,
            "fragmentation_emoji": emoji,
            "bedtime": bedtime_str,
            "sleep_start_utc": sleep_start,
            "summary": summary
        }
        
    except Exception as e:
        return {"status": "error", "error": str(e)}


def main():
    """Main function for morning sleep and glucose analysis."""
    client = get_client()
    
    # Fetch overnight data
    glucose = get_overnight_glucose(client)
    sleep = get_sleep_fragmentation(client)
    
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overnight_glucose": glucose,
        "sleep_fragmentation": sleep,
    }
    
    # Output formatting
    if "--json" in sys.argv:
        print(json.dumps(output, indent=2, default=str))
    else:
        print("🛌 SLEEP")
        if sleep.get("status") == "ok":
            print(f"  {sleep['summary']}")
        else:
            print(f"  No sleep data available: {sleep.get('error', 'unknown issue')}")
        
        print("\n🩸 OVERNIGHT GLUCOSE")
        if glucose.get("status") == "ok":
            print(f"  {glucose['summary']}")
            if glucose.get('spikes_over_140', 0) > 0:
                print(f"  ⚠️ {glucose['spikes_over_140']} spike(s) over 140 mg/dL")
            if glucose.get('dips_under_70', 0) > 0:
                print(f"  ⚠️ {glucose['dips_under_70']} dip(s) below 70 mg/dL")
        elif glucose.get("status") == "no_data":
            print(f"  {glucose.get('summary', '⚠️ No CGM data overnight')}")
        else:
            print(f"  Error: {glucose.get('error', 'unknown')}")


if __name__ == "__main__":
    main()