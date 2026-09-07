import json
import urllib.request
import urllib.error

def fetch_json(url, output_file):
    try:
        with urllib.request.urlopen(url) as response:
            data = json.load(response)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Dane zapisano do pliku: {output_file}")
    except urllib.error.URLError as e:
        print(f"Błąd połączenia: {e.reason}")
    except json.JSONDecodeError:
        print("Błąd: Odpowiedź nie jest prawidłowym JSON")
    except Exception as e:
        print(f"Wystąpił nieoczekiwany błąd: {e}")

if __name__ == "__main__":
    url = input("Podaj URL do JSON: ")
    output = input("Podaj nazwę pliku wyjściowego: ")
    fetch_json(url, output)