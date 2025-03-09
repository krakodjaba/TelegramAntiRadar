import logging
import sys
import asyncio
import sqlite3
import math
from aiogram import Bot, Dispatcher, types, Router

# Установка API токена
API_TOKEN = sys.argv[1]

users_geo = {}

logging.basicConfig(filename='logs.log', level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

bot = Bot(token=API_TOKEN)

router = Router()

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = map(math.radians, [lat1, lat2])
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c * 1000

def get_nearby_cameras(user_lat, user_lon, radius=2000):
    with sqlite3.connect('gibdd.db') as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT camera_model, camera_id, gps_x, gps_y, camera_place 
            FROM gibdd
            WHERE (
                6371 * acos(
                    cos(radians(?)) * cos(radians(gps_x)) * cos(radians(gps_y) - radians(?)) +
                    sin(radians(?)) * sin(radians(gps_x))
                )
            ) < ?;
        """, (user_lat, user_lon, user_lat, radius / 1000))
        cameras = cursor.fetchall()
    
    return [{"camera_model": c[0], "id": c[1], "lat": c[2], "lon": c[3], "location": c[4]} for c in cameras]

async def process_location(message: types.Message):
    global users_geo
    user_lon,user_lat  = message.location.latitude, message.location.longitude
    if users_geo.get(message.from_user.id) and users_geo.get(message.from_user.id) != [user_lat,user_lon]:
        users_geo[message.from_user.id] = [user_lat,user_lon]

        cameras = get_nearby_cameras(user_lat, user_lon, radius=500)
        cameras = sorted([{**c, "distance": haversine(user_lat, user_lon, c["lat"], c["lon"])} for c in cameras], key=lambda x: x['distance'])
        
        for camera in cameras:
            await bot.send_location(
                message.chat.id, latitude=camera['lon'], longitude=camera['lat'], horizontal_accuracy=1.0,  proximity_alert_radius=50
            )
            await bot.send_message(message.chat.id, f"{camera['camera_model']} - {camera['location']}, Расстояние: {int(camera['distance'])} м.")

@router.edited_message(lambda msg: msg.location)
async def location_update(edited_message: types.Message):
    await process_location(edited_message)

@router.message(lambda msg: msg.location)
async def location_handler(message: types.Message):
    await process_location(message)
       
dp = Dispatcher()
dp.include_router(router)

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
