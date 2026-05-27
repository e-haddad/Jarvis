import requests

def get_bitcoin_price():
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": "bitcoin", "vs_currencies": "usd"}
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        price = response.json()["bitcoin"]["usd"]
        print(f"₿ Bitcoin price: ${price:,.2f} USD")
    except requests.exceptions.ConnectionError:
        print("⚠️  API unreachable — check your internet connection.")
    except requests.exceptions.Timeout:
        print("⚠️  Request timed out — CoinGecko didn't respond in time.")
    except requests.exceptions.HTTPError as e:
        print(f"⚠️  API returned an error: {e}")
    except (KeyError, ValueError):
        print("⚠️  Unexpected response format — CoinGecko may have changed their API.")

if __name__ == "__main__":
    get_bitcoin_price()
