import json
import os
from datetime import datetime
from typing import List, Dict, Any

BOOKINGS_FILE = "bookings.json"

def load_bookings() -> List[Dict[str, Any]]:
    """Загружает список бронирований из файла"""
    if os.path.exists(BOOKINGS_FILE):
        try:
            with open(BOOKINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    return []

def save_bookings(bookings: List[Dict[str, Any]]) -> None:
    """Сохраняет список бронирований в файл"""
    with open(BOOKINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(bookings, f, ensure_ascii=False, indent=2)

def add_booking(booking_data: Dict[str, Any]) -> Dict[str, Any]:
    """Добавляет новое бронирование"""
    bookings = load_bookings()
    
    # Добавляем ID и timestamp
    booking_id = len(bookings) + 1
    booking_data['id'] = booking_id
    booking_data['timestamp'] = datetime.now().isoformat()
    booking_data['status'] = 'new'
    
    bookings.append(booking_data)
    save_bookings(bookings)
    
    return booking_data

def get_bookings_by_date(date: str) -> List[Dict[str, Any]]:
    """Получает бронирования по дате"""
    bookings = load_bookings()
    return [b for b in bookings if b.get('date') == date]

def get_all_bookings() -> List[Dict[str, Any]]:
    """Получает все бронирования"""
    return load_bookings()

def update_booking_status(booking_id: int, status: str) -> bool:
    """Обновляет статус бронирования"""
    bookings = load_bookings()
    for booking in bookings:
        if booking.get('id') == booking_id:
            booking['status'] = status
            save_bookings(bookings)
            return True
    return False 

def booking_exists(user_id, location, date, time):
    bookings = get_all_bookings()
    for booking in bookings:
        if (
            booking['user_id'] == user_id and
            booking['location'] == location and
            booking['date'] == date and
            booking['time'] == time
        ):
            return True
    return False 

def delete_all_bookings() -> None:
    """Удаляет все бронирования (очищает файл)"""
    save_bookings([])


def delete_booking_by_id(booking_id: int) -> bool:
    """Удаляет бронирование по ID. Возвращает True, если удалено, иначе False."""
    bookings = load_bookings()
    new_bookings = [b for b in bookings if b.get('id') != booking_id]
    if len(new_bookings) == len(bookings):
        return False  # Ничего не удалено
    save_bookings(new_bookings)
    return True 