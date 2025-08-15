import os
import requests
import json
import google.generativeai as genai
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import io
import base64
import numpy as np
from bs4 import BeautifulSoup
import re
import threading
import warnings
warnings.filterwarnings('ignore')

app = Flask(__name__)
CORS(app)

# Configure APIs
GEMINI_API_KEY = "your_gemini_api_key_here"  # Replace with your actual API key
WEATHER_API_KEY = "your_openweather_api_key_here"  # Replace with your actual API key

# Configure Gemini only if API key is provided
if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
    genai.configure(api_key=GEMINI_API_KEY)

# Indian states mapping for region-specific data
INDIAN_STATES = {
    "Delhi": {"state": "Delhi", "state_code": "DL"},
    "Mumbai": {"state": "Maharashtra", "state_code": "MH"},
    "Bangalore": {"state": "Karnataka", "state_code": "KA"},
    "Chennai": {"state": "Tamil Nadu", "state_code": "TN"},
    "Kolkata": {"state": "West Bengal", "state_code": "WB"},
    "Hyderabad": {"state": "Telangana", "state_code": "TG"},
    "Pune": {"state": "Maharashtra", "state_code": "MH"},
    "Ahmedabad": {"state": "Gujarat", "state_code": "GJ"},
    "Jaipur": {"state": "Rajasthan", "state_code": "RJ"},
    "Lucknow": {"state": "Uttar Pradesh", "state_code": "UP"},
    "Chandigarh": {"state": "Punjab", "state_code": "PB"},
    "Bhopal": {"state": "Madhya Pradesh", "state_code": "MP"},
    "Patna": {"state": "Bihar", "state_code": "BR"},
    "Raipur": {"state": "Chhattisgarh", "state_code": "CG"},
    "Indore": {"state": "Madhya Pradesh", "state_code": "MP"},
    "Surat": {"state": "Gujarat", "state_code": "GJ"},
    "Kochi": {"state": "Kerala", "state_code": "KL"},
    "Thiruvananthapuram": {"state": "Kerala", "state_code": "KL"},
    "Guwahati": {"state": "Assam", "state_code": "AS"},
    "Bhubaneswar": {"state": "Odisha", "state_code": "OR"}
}

def get_enhanced_weather_data(region):
    """Fetch comprehensive weather data including 7-day forecast and precipitation"""
    try:
        if not WEATHER_API_KEY or WEATHER_API_KEY == "your_openweather_api_key_here":
            print("Using mock weather data - no API key provided")
            return get_mock_weather_data(region)
            
        # Current weather
        current_url = f"http://api.openweathermap.org/data/2.5/weather?q={region},IN&appid={WEATHER_API_KEY}&units=metric"
        current_response = requests.get(current_url, timeout=10)
        
        if current_response.status_code != 200:
            print(f"Weather API error: {current_response.status_code}")
            return get_mock_weather_data(region)
            
        current_data = current_response.json()
        
        # Get coordinates for forecast
        lat = current_data['coord']['lat']
        lon = current_data['coord']['lon']
        
        # Try to get 7-day forecast using standard forecast API (free tier)
        forecast_url = f"http://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}&units=metric"
        forecast_response = requests.get(forecast_url, timeout=10)
        
        if forecast_response.status_code == 200:
            forecast_data = forecast_response.json()
            # Convert 5-day/3-hour forecast to daily format
            daily_forecast = convert_to_daily_forecast(forecast_data['list'])
        else:
            print("Using mock forecast data")
            daily_forecast = get_mock_weather_data(region)['forecast']
        
        return {
            'current': current_data,
            'forecast': daily_forecast,
            'hourly': []
        }
    except Exception as e:
        print(f"Weather API Error: {e}")
        return get_mock_weather_data(region)

def convert_to_daily_forecast(hourly_data):
    """Convert hourly forecast data to daily format"""
    daily_data = []
    current_date = None
    day_temps = []
    day_humidity = []
    day_precipitation = []
    day_weather = []
    
    for item in hourly_data[:40]:  # Use available data points
        dt = datetime.fromtimestamp(item['dt'])
        date_str = dt.strftime('%Y-%m-%d')
        
        if current_date != date_str:
            # Save previous day data
            if current_date and day_temps:
                daily_data.append({
                    'dt': int(datetime.strptime(current_date, '%Y-%m-%d').timestamp()),
                    'temp': {
                        'day': np.mean(day_temps),
                        'min': min(day_temps),
                        'max': max(day_temps)
                    },
                    'humidity': int(np.mean(day_humidity)) if day_humidity else 70,
                    'pop': max(day_precipitation) if day_precipitation else 0,
                    'weather': [{'description': day_weather[0] if day_weather else 'clear sky'}],
                    'wind_speed': 5.0
                })
            
            # Start new day
            current_date = date_str
            day_temps = []
            day_humidity = []
            day_precipitation = []
            day_weather = []
        
        # Accumulate day data
        day_temps.append(item['main']['temp'])
        day_humidity.append(item['main']['humidity'])
        day_precipitation.append(item.get('pop', 0))
        if item.get('weather') and len(item['weather']) > 0:
            day_weather.append(item['weather'][0]['description'])
    
    # Add the last day
    if current_date and day_temps:
        daily_data.append({
            'dt': int(datetime.strptime(current_date, '%Y-%m-%d').timestamp()),
            'temp': {
                'day': np.mean(day_temps),
                'min': min(day_temps),
                'max': max(day_temps)
            },
            'humidity': int(np.mean(day_humidity)) if day_humidity else 70,
            'pop': max(day_precipitation) if day_precipitation else 0,
            'weather': [{'description': day_weather[0] if day_weather else 'clear sky'}],
            'wind_speed': 5.0
        })
    
    # Ensure we have at least 7 days
    while len(daily_data) < 7:
        last_day = daily_data[-1] if daily_data else None
        base_temp = last_day['temp']['day'] if last_day else 28
        
        daily_data.append({
            'dt': int((datetime.now() + timedelta(days=len(daily_data))).timestamp()),
            'temp': {
                'day': base_temp + np.random.uniform(-3, 3),
                'min': base_temp - 5,
                'max': base_temp + 5
            },
            'humidity': np.random.randint(50, 90),
            'pop': np.random.uniform(0, 0.6),
            'weather': [{'description': np.random.choice(['sunny', 'cloudy', 'partly cloudy'])}],
            'wind_speed': np.random.uniform(3, 10)
        })
    
    return daily_data[:7]

def get_mock_weather_data(region):
    """Enhanced mock weather data with precipitation"""
    base_temp = 28
    mock_daily = []
    
    for i in range(7):
        date = datetime.now() + timedelta(days=i)
        temp_variation = np.random.uniform(-5, 6)
        precipitation_chance = np.random.uniform(0.1, 0.8)
        
        mock_daily.append({
            'dt': int(date.timestamp()),
            'temp': {
                'day': base_temp + temp_variation,
                'min': base_temp + temp_variation - 5,
                'max': base_temp + temp_variation + 5
            },
            'humidity': np.random.randint(50, 90),
            'pop': precipitation_chance,
            'weather': [{'description': np.random.choice(['sunny', 'cloudy', 'light rain', 'partly cloudy'])}],
            'wind_speed': np.random.uniform(2, 15)
        })
    
    return {
        'current': {
            'main': {'temp': base_temp, 'humidity': 65},
            'weather': [{'description': 'partly cloudy'}],
            'name': region,
            'wind': {'speed': 5.2}
        },
        'forecast': mock_daily,
        'hourly': []
    }

def generate_dynamic_irrigation_advice(crop, region, weather_data):
    """Generate dynamic irrigation advice using LLM"""
    try:
        if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
            return generate_fallback_irrigation_advice(crop, region, weather_data)
            
        model = genai.GenerativeModel('gemini-pro')
        
        state_info = INDIAN_STATES.get(region, {"state": "India"})
        state = state_info["state"]
        
        current_weather = weather_data['current']
        forecast = weather_data['forecast']
        
        if not forecast or len(forecast) == 0:
            return generate_fallback_irrigation_advice(crop, region, weather_data)
        
        # Prepare detailed weather data for LLM
        forecast_text = []
        for i, day in enumerate(forecast[:7]):
            precipitation = day.get('pop', 0) * 100
            temp_day = day.get('temp', {}).get('day', 28)
            temp_min = day.get('temp', {}).get('min', 23)
            temp_max = day.get('temp', {}).get('max', 33)
            humidity = day.get('humidity', 70)
            weather_desc = day.get('weather', [{}])[0].get('description', 'clear')
            
            forecast_text.append(
                f"Day {i+1}: {temp_day:.1f}°C, "
                f"Min: {temp_min:.1f}°C, Max: {temp_max:.1f}°C, "
                f"Humidity: {humidity}%, "
                f"Precipitation chance: {precipitation:.1f}%, "
                f"Weather: {weather_desc}"
            )
        
        prompt = f"""
        You are an expert agricultural advisor. Provide clear irrigation recommendations for {crop} in {region}, {state}.

        Current Weather: {current_weather['main']['temp']}°C, {current_weather['main']['humidity']}% humidity, {current_weather['weather'][0]['description']}

        7-Day Forecast:
        {chr(10).join(forecast_text)}

        Please provide structured irrigation advice with the following sections:

        ## IMMEDIATE IRRIGATION NEEDS
        Should irrigation be done now? [Yes/No with clear reasoning]
        Best timing: [Specific hours]
        Duration: [How long]
        Water quantity: [Amount per acre]

        ## 7-DAY IRRIGATION SCHEDULE
        Day 1: [Irrigation recommendation with timing]
        Day 2: [Irrigation recommendation with timing]
        Day 3: [Irrigation recommendation with timing]
        Day 4: [Irrigation recommendation with timing]
        Day 5: [Irrigation recommendation with timing]
        Day 6: [Irrigation recommendation with timing]
        Day 7: [Irrigation recommendation with timing]

        ## REGION-SPECIFIC CONSIDERATIONS FOR {state}
        • Soil types common in {state}
        • Local water availability factors
        • State-specific irrigation practices
        • Climate considerations for {region}

        ## CROP GROWTH STAGE ANALYSIS
        • Current growth stage for {crop} in {get_current_season()}
        • Water requirements for this stage
        • Critical irrigation periods ahead

        ## EMERGENCY PROTOCOLS
        • Actions if sudden rain occurs
        • Steps if temperature spikes
        • Drought management strategies

        Keep the format clean and structured. Use bullet points and clear headings.
        """
        
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        print(f"LLM Irrigation Error: {e}")
        return generate_fallback_irrigation_advice(crop, region, weather_data)

def generate_dynamic_seed_varieties(crop, region, weather_data):
    """Generate seed variety recommendations using LLM with region-specific data"""
    try:
        if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
            return generate_fallback_seed_advice(crop, region)
            
        model = genai.GenerativeModel('gemini-pro')
        
        state_info = INDIAN_STATES.get(region, {"state": "India"})
        state = state_info["state"]
        
        current_temp = weather_data['current']['main']['temp']
        forecast = weather_data.get('forecast', [])
        
        if forecast and len(forecast) > 0:
            avg_temp_7day = np.mean([day.get('temp', {}).get('day', current_temp) for day in forecast])
            avg_precipitation = np.mean([day.get('pop', 0) * 100 for day in forecast])
        else:
            avg_temp_7day = current_temp
            avg_precipitation = 30
        
        prompt = f"""
        Provide seed variety recommendations for {crop} cultivation in {region}, {state}.

        Current Conditions: {current_temp}°C temperature, {avg_temp_7day:.1f}°C average, {avg_precipitation:.1f}% precipitation chance

        Please provide clear recommendations in the following format:

        ## TOP 5 RECOMMENDED VARIETIES

        1. **[Variety Name]** - [Duration] days, [Yield] quintals/hectare, [Key features]
        2. **[Variety Name]** - [Duration] days, [Yield] quintals/hectare, [Key features]
        3. **[Variety Name]** - [Duration] days, [Yield] quintals/hectare, [Key features]
        4. **[Variety Name]** - [Duration] days, [Yield] quintals/hectare, [Key features]
        5. **[Variety Name]** - [Duration] days, [Yield] quintals/hectare, [Key features]

        ## STATE-SPECIFIC VARIETIES FOR {state}

        **Agricultural University Recommendations:**
        • [Variety 1]: [Specific benefits for {state}]
        • [Variety 2]: [Specific benefits for {state}]
        • [Variety 3]: [Specific benefits for {state}]

        **Popular Local Varieties:**
        • [Variety 1]: [Why farmers prefer it]
        • [Variety 2]: [Why farmers prefer it]

        ## WEATHER-ADAPTED CHOICES

        **Heat Tolerant (for high temperatures):**
        • [Variety]: [Temperature tolerance details]

        **Drought Resistant:**
        • [Variety]: [Water efficiency features]

        **High Precipitation Tolerant:**
        • [Variety]: [Waterlogging resistance]

        ## SEED SOURCING IN {state}

        **Government Sources:**
        • State Seed Corporation outlets
        • Agricultural cooperative societies
        • Krishi Vigyan Kendra distribution
        • Subsidy programs available

        **Private Certified Dealers:**
        • [Company 1]: [Contact/location info]
        • [Company 2]: [Contact/location info]

        **Quality Check Points:**
        • Verify ISI certification mark
        • Check germination rate (minimum 85%)
        • Confirm manufacturing/expiry dates
        • Ensure proper packaging

        ## LOCAL CONTACTS
        • {state} Agriculture Department: [For latest varieties]
        • Nearest KVK: [For technical guidance]
        • Seed testing lab: [For quality verification]

        Keep recommendations specific to {state} climate and proven successful in {region}.
        """
        
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        print(f"LLM Seed Varieties Error: {e}")
        return generate_fallback_seed_advice(crop, region)

def generate_comprehensive_ai_advice(crop, region, weather_data, irrigation_advice, seed_advice):
    """Generate comprehensive agricultural advice using LLM"""
    try:
        if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
            return generate_fallback_comprehensive_advice(crop, region, weather_data)
            
        model = genai.GenerativeModel('gemini-pro')
        
        state_info = INDIAN_STATES.get(region, {"state": "India"})
        state = state_info["state"]
        
        forecast = weather_data.get('forecast', [])
        if not forecast or len(forecast) == 0:
            return generate_fallback_comprehensive_advice(crop, region, weather_data)
        
        # Calculate weather trends
        first_temp = forecast[0].get('temp', {}).get('day', 28)
        last_temp = forecast[-1].get('temp', {}).get('day', 28)
        temp_trend = "increasing" if last_temp > first_temp else "decreasing"
        avg_precipitation = np.mean([day.get('pop', 0) * 100 for day in forecast])
        
        prompt = f"""
        Provide comprehensive agricultural guidance for {crop} farming in {region}, {state}.

        Current Conditions: {temp_trend} temperature trend, {avg_precipitation:.1f}% precipitation probability, {weather_data['current']['weather'][0]['description']}

        Please provide detailed advice in the following structured format:

        ## CROP MANAGEMENT STRATEGY

        **Current Growth Stage:** [Stage for {crop} in {get_current_season()}]
        **Key Activities This Week:**
        • [Activity 1]: [Specific details]
        • [Activity 2]: [Specific details]
        • [Activity 3]: [Specific details]

        **Field Maintenance:**
        • Soil preparation: [Current needs]
        • Plant spacing: [Recommendations]
        • Weed management: [Control methods]

        ## PEST & DISEASE MANAGEMENT

        **Common Threats in {state} During {get_current_season()}:**
        • [Pest/Disease 1]: [Risk level] - [Prevention and treatment]
        • [Pest/Disease 2]: [Risk level] - [Prevention and treatment]
        • [Pest/Disease 3]: [Risk level] - [Prevention and treatment]

        **Weather-Based Risks:**
        • High humidity risks: [Specific diseases and prevention]
        • Temperature effects: [Heat/cold stress management]

        **Treatment Options:**
        • Organic solutions: [Specific recommendations]
        • Chemical options: [If necessary, with proper dosage]

        ## FERTILIZER RECOMMENDATIONS

        **NPK Requirements for Current Stage:**
        • Nitrogen (N): [Amount and timing]
        • Phosphorus (P): [Amount and timing]
        • Potassium (K): [Amount and timing]

        **{state} Soil Considerations:**
        • Common soil types: [Local soil characteristics]
        • Required amendments: [Specific recommendations]

        **Organic Alternatives:**
        • Farmyard manure: [Application rate and timing]
        • Compost: [Local sources and usage]
        • Green manure: [Suitable options for {state}]

        ## MARKET INTELLIGENCE

        **Current Market Trends for {crop} in {state}:**
        • Price range: [Current rates]
        • Demand outlook: [Market predictions]
        • Quality requirements: [What buyers want]

        **Harvest & Sales Strategy:**
        • Optimal harvest timing: [For maximum profit]
        • Storage recommendations: [Post-harvest care]
        • Marketing channels: [Best selling options]

        **Government Support:**
        • MSP (Minimum Support Price): [Current rates if applicable]
        • Procurement centers: [Nearest locations]
        • Required documentation: [What farmers need]

        ## WEATHER-BASED ACTION PLAN

        **Next 7 Days Actions:**
        • Days 1-2: [Immediate activities based on weather]
        • Days 3-4: [Mid-week preparations]
        • Days 5-7: [Weekend activities]

        **Risk Management:**
        • Heavy rain protection: [Specific steps]
        • Heat wave management: [Cooling strategies]
        • Drought preparedness: [Water conservation]

        ## GOVERNMENT SCHEMES & SUPPORT

        **Central Schemes:**
        • PM-KISAN: [Eligibility and benefits]
        • Crop insurance (PMFBY): [Coverage details]
        • Input subsidies: [Available support]

        **{state} State Schemes:**
        • [State scheme 1]: [Details and eligibility]
        • [State scheme 2]: [Benefits available]
        • Agricultural loans: [Interest rates and terms]

        ## LOCAL RESOURCES

        **Technical Support in {region}:**
        • Krishi Vigyan Kendra: [Services available]
        • Agricultural extension officer: [Contact method]
        • Soil testing lab: [Location and services]

        **Emergency Contacts:**
        • {state} Kisan Call Center: [Helpline number]
        • Weather advisory: [Information source]
        • Pest/disease helpline: [Expert consultation]
        • Market information: [Price updates]

        ## WEEKLY ACTION SUMMARY

        **This Week's Priorities:**
        1. [Priority 1]
        2. [Priority 2]
        3. [Priority 3]

        **Monitor Closely:**
        • [What to watch]
        • [When to take action]
        • [Who to contact for help]

        Keep all recommendations specific to {region}, {state} conditions and current weather patterns.
        """
        
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        print(f"Comprehensive AI advice error: {e}")
        return generate_fallback_comprehensive_advice(crop, region, weather_data)

def get_current_season():
    """Determine current agricultural season in India"""
    month = datetime.now().month
    if month in [6, 7, 8, 9, 10]:
        return "Kharif (Monsoon season)"
    elif month in [11, 12, 1, 2, 3, 4]:
        return "Rabi (Winter season)"
    else:
        return "Zaid (Summer season)"

def create_enhanced_weather_graph(weather_data):
    """Create enhanced weather graph with precipitation data"""
    try:
        forecast_data = weather_data.get('forecast', [])
        if not forecast_data or len(forecast_data) == 0:
            print("No forecast data available for graph")
            return None
            
        forecast_data = forecast_data[:7]  # Ensure only 7 days
        
        dates = []
        temps = []
        temp_mins = []
        temp_maxs = []
        precipitation = []
        humidity = []
        
        for day in forecast_data:
            try:
                date = datetime.fromtimestamp(day.get('dt', datetime.now().timestamp()))
                dates.append(date)
                
                temp_data = day.get('temp', {})
                temps.append(temp_data.get('day', 28))
                temp_mins.append(temp_data.get('min', 23))
                temp_maxs.append(temp_data.get('max', 33))
                
                precipitation.append(day.get('pop', 0) * 100)
                humidity.append(day.get('humidity', 70))
            except Exception as e:
                print(f"Error processing day data: {e}")
                continue
        
        if len(dates) == 0:
            print("No valid date data for graph")
            return None
        
        # Create subplot with multiple plots
        plt.style.use('default')
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 12))
        
        # Temperature plot
        if temps and len(temps) > 0:
            ax1.plot(dates, temps, 'r-o', label='Average Temperature', linewidth=3, markersize=6)
            if temp_mins and temp_maxs and len(temp_mins) == len(temp_maxs) == len(dates):
                ax1.fill_between(dates, temp_mins, temp_maxs, alpha=0.3, color='orange', label='Temperature Range')
        ax1.set_title('7-Day Temperature Forecast', fontsize=16, fontweight='bold')
        ax1.set_ylabel('Temperature (°C)', fontsize=12)
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Precipitation plot
        if precipitation and len(precipitation) > 0:
            bars = ax2.bar(dates, precipitation, alpha=0.7, color='blue', label='Precipitation Probability')
            ax2.set_title('Precipitation Probability (%)', fontsize=16, fontweight='bold')
            ax2.set_ylabel('Precipitation (%)', fontsize=12)
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            
            # Add percentage labels on bars
            for bar, pct in zip(bars, precipitation):
                height = bar.get_height()
                if height > 0:
                    ax2.text(bar.get_x() + bar.get_width()/2., height + 1,
                            f'{pct:.1f}%', ha='center', va='bottom', fontsize=10)
        
        # Humidity plot
        if humidity and len(humidity) > 0:
            ax3.plot(dates, humidity, 'g-s', label='Humidity', linewidth=2, markersize=5)
        ax3.set_title('Humidity Levels (%)', fontsize=16, fontweight='bold')
        ax3.set_ylabel('Humidity (%)', fontsize=12)
        ax3.set_xlabel('Date', fontsize=12)
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        # Format x-axis for all subplots
        for ax in [ax1, ax2, ax3]:
            ax.tick_params(axis='x', rotation=45)
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        
        plt.tight_layout()
        
        # Convert to base64 string
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        graph_base64 = base64.b64encode(buffer.getvalue()).decode()
        plt.close()
        
        return graph_base64
    except Exception as e:
        print(f"Enhanced graph creation error: {e}")
        return None

def generate_fallback_irrigation_advice(crop, region, weather_data):
    """Fallback irrigation advice"""
    current_temp = weather_data.get('current', {}).get('main', {}).get('temp', 28)
    current_humidity = weather_data.get('current', {}).get('main', {}).get('humidity', 65)
    
    state_info = INDIAN_STATES.get(region, {"state": "India"})
    state = state_info["state"]
    season = get_current_season()
    
    return f"""
🌾 IRRIGATION RECOMMENDATIONS FOR {crop.upper()} in {region}, {state}

📅 CURRENT SEASON: {season}
🌡️ CURRENT CONDITIONS: {current_temp}°C, {current_humidity}% humidity

💧 IMMEDIATE IRRIGATION NEEDS:
- Monitor soil moisture at 6-inch depth daily
- With current temperature ({current_temp}°C), irrigation may be needed in 2-3 days
- Best timing: Early morning (6-8 AM) or evening (5-7 PM)

📋 WEEKLY IRRIGATION SCHEDULE:
- Day 1-2: Check soil moisture, irrigate if dry
- Day 3-4: Light irrigation if no rainfall expected
- Day 5-7: Adjust based on weather conditions

🏛️ {state.upper()}-SPECIFIC CONSIDERATIONS:
- Follow local agricultural department guidelines
- Consider {state}'s typical soil conditions
- Account for regional water availability

⚠️ IMPORTANT TIPS:
- Avoid irrigation during peak sunlight hours
- Ensure proper drainage to prevent waterlogging
- Monitor crop stress indicators daily

📞 For expert advice, contact your nearest Krishi Vigyan Kendra in {state}.
    """

def generate_fallback_seed_advice(crop, region):
    """Fallback seed variety advice"""
    state_info = INDIAN_STATES.get(region, {"state": "India"})
    state = state_info["state"]
    season = get_current_season()
    
    return f"""
🌱 SEED VARIETY RECOMMENDATIONS FOR {crop.upper()} in {region}, {state}

📅 PLANTING SEASON: {season}

🏆 GENERAL RECOMMENDATIONS:
1. Choose varieties certified by the Indian Council of Agricultural Research (ICAR)
2. Select drought-resistant varieties for water-scarce areas
3. Prefer disease-resistant varieties common in {state}
4. Consider short-duration varieties for quick turnover

🌾 FOR {crop.upper()} IN {state.upper()}:
- Contact your local Agricultural Extension Officer
- Visit the nearest Krishi Vigyan Kendra for certified seeds
- Check with {state} Agricultural University recommendations
- Consult local seed dealers for region-tested varieties

📍 WHERE TO SOURCE:
- Government seed distribution centers in {state}
- Certified seed dealers in {region}
- Agricultural cooperatives
- Online platforms with certified seeds

⚠️ IMPORTANT NOTES:
- Always buy certified seeds with proper labeling
- Check seed packet for expiry date and germination rate
- Store seeds in cool, dry place before sowing
- Follow recommended seed rate per acre

📞 Contact {state} Department of Agriculture for latest variety recommendations.
    """

def generate_fallback_comprehensive_advice(crop, region, weather_data):
    """Fallback comprehensive advice"""
    temp = weather_data.get('current', {}).get('main', {}).get('temp', 28)
    humidity = weather_data.get('current', {}).get('main', {}).get('humidity', 65)
    state_info = INDIAN_STATES.get(region, {"state": "India"})
    state = state_info["state"]
    season = get_current_season()
    
    return f"""
🌾 COMPREHENSIVE AGRICULTURAL GUIDANCE FOR {crop.upper()}

📍 LOCATION: {region}, {state}, India
🗓️ SEASON: {season}
🌡️ CURRENT CONDITIONS: {temp}°C, {humidity}% humidity

🌾 CROP MANAGEMENT:
- Monitor crop daily for growth and stress signs
- Ensure proper plant spacing and field drainage
- Regular weeding and soil cultivation needed
- Apply organic matter to improve soil health

🐛 PEST & DISEASE MANAGEMENT:
- Scout fields regularly for pest and disease symptoms
- Use integrated pest management (IPM) practices
- Apply preventive measures based on weather conditions
- Consult local agricultural extension for specific treatments

🌱 FERTILIZER RECOMMENDATIONS:
- Apply balanced NPK fertilizer based on soil test
- Use organic fertilizers like farmyard manure
- Time fertilizer application with weather conditions
- Avoid fertilizer application before heavy rains

💧 IRRIGATION MANAGEMENT:
- Monitor soil moisture levels regularly
- Irrigate during critical growth stages
- Use efficient irrigation methods like drip or sprinkler
- Avoid over-irrigation to prevent waterlogging

📈 MARKET INTELLIGENCE:
- Monitor local market prices regularly
- Plan harvest timing for best market rates
- Consider value-addition opportunities
- Explore government procurement schemes

⚠️ WEATHER ALERTS:
- Monitor weather forecasts daily
- Prepare for extreme weather events
- Adjust farming operations based on weather
- Have contingency plans for crop protection

🏛️ GOVERNMENT SUPPORT:
- Check eligibility for crop insurance schemes
- Explore subsidies available in {state}
- Contact Krishi Vigyan Kendra for technical support
- Register for government benefit schemes

📞 EMERGENCY CONTACTS:
- {state} Agricultural Helpline
- Local Krishi Vigyan Kendra
- District Agricultural Officer
- Veterinary services (if applicable)

For detailed, region-specific advice, contact your local agricultural extension officer.
    """

def transcribe_audio(audio_file):
    """Transcribe audio file to text using Groq Whisper"""
    try:
        if not groq_client:
            return "Audio transcription service not available"
            
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio_file:
            # Convert audio to WAV format
            audio = AudioSegment.from_file(audio_file)
            audio.export(temp_audio_file.name, format="wav")
            
            # Transcribe using Groq Whisper
            with open(temp_audio_file.name, "rb") as audio_file_handle:
                transcription = groq_client.audio.transcriptions.create(
                    model="whisper-large-v3", 
                    file=audio_file_handle
                )
            
            # Clean up temp file
            os.unlink(temp_audio_file.name)
            
        return transcription.text
    except Exception as e:
        print(f"Audio transcription error: {e}")
        return "Error transcribing audio"

def translate_to_english(text):
    """Detect language and translate to English if needed"""
    try:
        if not translate_client:
            return text, "en"
            
        # Detect language
        detection = translate_client.detect_language(text)
        detected_language = detection['language']
        
        print(f"Detected language: {detected_language}")
        
        if detected_language == "hi":  # Hindi
            print("Detected Hindi, translating to English...")
            translation = translate_client.translate(text, target_language="en")
            return translation['translatedText'], detected_language
        
        print("Detected English or other language, no translation needed.")
        return text, detected_language
        
    except Exception as e:
        print(f"Translation error: {e}")
        return text, "en"

def translate_to_original_language(text, target_language):
    """Translate response back to original language"""
    try:
        if not translate_client or target_language == "en":
            return text
            
        translation = translate_client.translate(text, target_language=target_language)
        return translation['translatedText']
    except Exception as e:
        print(f"Back-translation error: {e}")
        return text

@app.route('/api/transcribe', methods=['POST'])
def transcribe_audio_endpoint():
    """Handle audio transcription and translation"""
    try:
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
        
        audio_file = request.files['audio']
        
        # Transcribe audio to text
        transcribed_text = transcribe_audio(audio_file)
        print(f"Transcribed text: {transcribed_text}")
        
        # Translate to English if needed
        english_text, detected_language = translate_to_english(transcribed_text)
        print(f"English text: {english_text}")
        print(f"Detected language: {detected_language}")
        
        return jsonify({
            'transcribed_text': transcribed_text,
            'english_text': english_text,
            'detected_language': detected_language
        })
        
    except Exception as e:
        print(f"Transcription API error: {e}")
        return jsonify({'error': 'Error processing audio'}), 500

@app.route('/api/voice-analyze', methods=['POST'])
def voice_analyze_crop():
    """Analyze crop with voice query support"""
    try:
        data = request.get_json()
        region = data.get('region', '')
        crop = data.get('crop', '')
        voice_query = data.get('voice_query', '')
        detected_language = data.get('detected_language', 'en')
        
        if not region or not crop:
            return jsonify({'error': 'Region and crop are required'}), 400
        
        print(f"Voice analyzing {crop} in {region} with query: {voice_query}")
        print(f"Detected language: {detected_language}")
        
        # Get enhanced weather data
        weather_data = get_enhanced_weather_data(region)
        
        # Generate enhanced AI advice with voice query context
        comprehensive_advice = generate_voice_enhanced_ai_advice(
            crop, region, weather_data, voice_query, detected_language
        )
        
        # Translate response back to original language if needed
        if detected_language != "en":
            comprehensive_advice = translate_to_original_language(comprehensive_advice, detected_language)
        
        # Prepare response (similar to regular analyze but focused on voice query)
        forecast_data = []
        forecast = weather_data.get('forecast', [])
        for day in forecast[:7]:
            try:
                temp_data = day.get('temp', {})
                forecast_data.append({
                    'date': datetime.fromtimestamp(day.get('dt', datetime.now().timestamp())).strftime('%Y-%m-%d'),
                    'temp': temp_data.get('day', 28),
                    'temp_min': temp_data.get('min', 23),
                    'temp_max': temp_data.get('max', 33),
                    'humidity': day.get('humidity', 70),
                    'precipitation_prob': day.get('pop', 0) * 100,
                    'description': day.get('weather', [{}])[0].get('description', 'clear'),
                    'wind_speed': day.get('wind_speed', 5.0)
                })
            except Exception as e:
                print(f"Error processing forecast day: {e}")
                continue
        
        state_info = INDIAN_STATES.get(region, {"state": "India", "state_code": "IN"})
        
        response = {
            'region': region,
            'state': state_info['state'],
            'crop': crop,
            'voice_query': voice_query,
            'detected_language': detected_language,
            'current_season': get_current_season(),
            'current_weather': {
                'temperature': weather_data['current']['main']['temp'],
                'humidity': weather_data['current']['main']['humidity'],
                'description': weather_data['current']['weather'][0]['description'],
                'wind_speed': weather_data['current'].get('wind', {}).get('speed', 0)
            },
            'forecast': forecast_data,
            'voice_response': comprehensive_advice,
            'analysis_timestamp': datetime.now().isoformat()
        }
        
        return jsonify(response)
        
    except Exception as e:
        print(f"Voice API Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error. Please try again.'}), 500

def generate_voice_enhanced_ai_advice(crop, region, weather_data, voice_query, detected_language):
    """Generate AI advice enhanced with voice query context"""
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        state_info = INDIAN_STATES.get(region, {"state": "India"})
        state = state_info["state"]
        
        current_weather = weather_data['current']
        forecast = weather_data.get('forecast', [])
        
        # Prepare weather summary
        if forecast and len(forecast) > 0:
            avg_temp = np.mean([day.get('temp', {}).get('day', 28) for day in forecast])
            avg_precipitation = np.mean([day.get('pop', 0) * 100 for day in forecast])
        else:
            avg_temp = current_weather['main']['temp']
            avg_precipitation = 30
        
        prompt = f"""
        You are an expert agricultural advisor for Indian farmers. A farmer from {region}, {state} has asked a specific question about their {crop} farming.

        FARMER'S QUESTION: "{voice_query}"
        
        CURRENT CONDITIONS:
        - Location: {region}, {state}, India
        - Crop: {crop}
        - Season: {get_current_season()}
        - Current temperature: {current_weather['main']['temp']}°C
        - Current humidity: {current_weather['main']['humidity']}%
        - Weather: {current_weather['weather'][0]['description']}
        - 7-day average temperature: {avg_temp:.1f}°C
        - Average precipitation chance: {avg_precipitation:.1f}%

        Please provide a comprehensive answer to the farmer's specific question while also including relevant additional advice for {crop} farming in {state}.

        Structure your response as follows:

        ## ANSWER TO YOUR QUESTION
        [Direct answer to the farmer's specific question]

        ## ADDITIONAL RECOMMENDATIONS FOR {crop.upper()} IN {state.upper()}

        **Current Weather Advice:**
        [Weather-specific recommendations]

        **Immediate Actions Needed:**
        • [Action 1]
        • [Action 2]
        • [Action 3]

        **This Week's Focus:**
        • [Focus area 1]
        • [Focus area 2]
        • [Focus area 3]

        **Important Reminders:**
        • [Reminder 1]
        • [Reminder 2]
        • [Reminder 3]

        ## LOCAL SUPPORT IN {region}
        • Contact your nearest Krishi Vigyan Kendra for expert guidance
        • Consult {state} Agricultural Department for state-specific schemes
        • Monitor local weather forecasts daily

        Keep the response conversational, practical, and specific to {region}, {state} farming conditions.
        Address the farmer directly and provide actionable advice they can implement immediately.
        """
        
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        print(f"Voice-enhanced AI advice error: {e}")
        return f"""
        Thank you for your question about {crop} farming in {region}.
        
        ## ANSWER TO YOUR QUESTION
        Based on current weather conditions ({weather_data['current']['main']['temp']}°C, {weather_data['current']['main']['humidity']}% humidity), here's my advice for your {crop} crop.
        
        ## GENERAL RECOMMENDATIONS FOR {crop.upper()}
        • Monitor your crop daily for any stress signs
        • Ensure proper irrigation based on soil moisture
        • Apply fertilizers according to growth stage requirements
        • Watch for pest and disease symptoms
        
        ## IMMEDIATE ACTIONS
        • Check soil moisture levels
        • Monitor weather forecasts
        • Inspect crop for any issues
        
        For detailed, expert advice specific to your situation, please contact your local Krishi Vigyan Kendra or agricultural extension officer in {state}.
        """

@app.route('/api/analyze', methods=['POST'])
def analyze_crop():
    try:
        data = request.get_json()
        region = data.get('region', '')
        crop = data.get('crop', '')
        
        if not region or not crop:
            return jsonify({'error': 'Region and crop are required'}), 400
        
        print(f"Analyzing {crop} in {region}")
        
        # Get enhanced weather data with 7-day forecast and precipitation
        weather_data = get_enhanced_weather_data(region)
        print("Weather data retrieved")
        
        # Generate dynamic irrigation advice using LLM
        irrigation_advice = generate_dynamic_irrigation_advice(crop, region, weather_data)
        print("Irrigation advice generated")
        
        # Generate dynamic seed varieties using LLM
        seed_varieties = generate_dynamic_seed_varieties(crop, region, weather_data)
        print("Seed varieties generated")
        
        # Create enhanced weather graph with precipitation
        weather_graph = create_enhanced_weather_graph(weather_data)
        print("Weather graph created")
        
        # Generate comprehensive AI advice
        comprehensive_advice = generate_comprehensive_ai_advice(
            crop, region, weather_data, irrigation_advice, seed_varieties
        )
        print("Comprehensive advice generated")
        
        # Prepare enhanced forecast data for frontend
        forecast_data = []
        forecast = weather_data.get('forecast', [])
        for day in forecast[:7]:
            try:
                temp_data = day.get('temp', {})
                forecast_data.append({
                    'date': datetime.fromtimestamp(day.get('dt', datetime.now().timestamp())).strftime('%Y-%m-%d'),
                    'temp': temp_data.get('day', 28),
                    'temp_min': temp_data.get('min', 23),
                    'temp_max': temp_data.get('max', 33),
                    'humidity': day.get('humidity', 70),
                    'precipitation_prob': day.get('pop', 0) * 100,
                    'description': day.get('weather', [{}])[0].get('description', 'clear'),
                    'wind_speed': day.get('wind_speed', 5.0)
                })
            except Exception as e:
                print(f"Error processing forecast day: {e}")
                continue
        
        state_info = INDIAN_STATES.get(region, {"state": "India", "state_code": "IN"})
        
        response = {
            'region': region,
            'state': state_info['state'],
            'crop': crop,
            'current_season': get_current_season(),
            'current_weather': {
                'temperature': weather_data['current']['main']['temp'],
                'humidity': weather_data['current']['main']['humidity'],
                'description': weather_data['current']['weather'][0]['description'],
                'wind_speed': weather_data['current'].get('wind', {}).get('speed', 0)
            },
            'irrigation_advice': irrigation_advice,
            'seed_varieties': seed_varieties,
            'weather_graph': weather_graph,
            'forecast': forecast_data,
            'comprehensive_advice': comprehensive_advice,
            'analysis_timestamp': datetime.now().isoformat()
        }
        
        print("Response prepared successfully")
        return jsonify(response)
        
    except Exception as e:
        print(f"API Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error. Please try again.'}), 500

if __name__ == '__main__':
    print("Starting AgriGenie Enhanced Server...")
    print("Make sure to add your API keys in the code!")
    print("Gemini API Key required for AI features")
    print("Weather API Key optional (will use mock data if not provided)")
    app.run(debug=True, host='0.0.0.0', port=5000)