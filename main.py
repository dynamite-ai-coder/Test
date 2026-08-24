from datetime import datetime

# Pobieranie aktualnej daty i hgodziny
current_datetime = datetime.now()

# Wyświetlenie daty i godziny
print(f"Aktualna data i godzina: {current_datetime}")
print(f"Format szczegółowy: {current_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
