# finance_monitor.py
# Background stock price monitoring service for Jarvis.
# Polls watchlist at regular intervals, detects threshold crossings, emits voice alerts.

import os
import time
import yaml
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Callable

from search import get_stock_price

VAULT_ROOT = Path.home() / "Desktop" / "OBS" / "Edward"
WATCHLIST_PATH = VAULT_ROOT / "Finance" / "watchlist.yml"


class StockMonitor:
    """
    Monitors a watchlist of stocks and triggers alerts when price thresholds are crossed.
    Runs in a background thread with configurable polling interval.
    """

    def __init__(self, emit_alert_callback: Optional[Callable] = None):
        """
        Initialize the stock monitor.

        Args:
            emit_alert_callback: Function called with alert data when threshold crossed.
                                 Signature: (symbol, price, change_pct, direction) -> None
        """
        self.emit_alert = emit_alert_callback or self._default_alert_handler
        self.watchlist: List[Dict] = []
        self.alert_settings: Dict = {}
        self.price_history: Dict[str, List[Tuple[float, float]]] = {}  # {symbol: [(timestamp, price), ...]}
        self.alert_cooldown: Dict[str, float] = {}  # {symbol: last_alert_timestamp}
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def _default_alert_handler(self, symbol: str, price: float, change_pct: float, direction: str):
        """Default alert handler just prints to console."""
        print(f"[FINANCE ALERT] {symbol} {direction} {abs(change_pct):.2f}% to ${price:,.2f}")

    def _load_watchlist(self) -> bool:
        """Load watchlist from vault. Returns True if successful."""
        try:
            if not WATCHLIST_PATH.exists():
                print(f"[StockMonitor] Watchlist not found at {WATCHLIST_PATH}")
                return False

            with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            self.watchlist = data.get("stocks", [])
            self.alert_settings = data.get("alert_settings", {})

            if not self.watchlist:
                print("[StockMonitor] Watchlist is empty")
                return False

            print(f"[StockMonitor] Loaded {len(self.watchlist)} stocks")
            return True

        except Exception as e:
            print(f"[StockMonitor] Failed to load watchlist: {e}")
            return False

    def _is_market_hours(self) -> bool:
        """Check if NYSE is currently open (9:30am-4pm ET, weekdays)."""
        try:
            from datetime import timezone, timedelta
            et = timezone(timedelta(hours=-5))  # EST (adjust for DST if needed)
            now = datetime.now(et)

            # Weekend check
            if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
                return False

            # Market hours: 9:30 AM - 4:00 PM ET
            market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
            market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)

            return market_open <= now <= market_close

        except Exception as e:
            print(f"[StockMonitor] Market hours check failed: {e}")
            return True  # Fail open — check anyway if detection fails

    def _should_skip_check(self) -> bool:
        """Determine if price check should be skipped (outside market hours)."""
        if not self.alert_settings.get("market_hours_only", True):
            return False
        return not self._is_market_hours()

    def _in_alert_cooldown(self, symbol: str, cooldown_seconds: int = 3600) -> bool:
        """Check if symbol is in cooldown period (default 1 hour)."""
        last_alert = self.alert_cooldown.get(symbol)
        if last_alert is None:
            return False
        return (time.time() - last_alert) < cooldown_seconds

    def _detect_alert(self, symbol: str, current_price: float, change_pct: float, threshold: float) -> bool:
        """
        Detect if alert should be triggered based on threshold crossing.
        Returns True if alert triggered.
        """
        if abs(change_pct) < threshold:
            return False

        if self._in_alert_cooldown(symbol):
            return False

        # Trigger alert
        direction = "↑" if change_pct >= 0 else "↓"
        self.emit_alert(symbol, current_price, change_pct, direction)
        self.alert_cooldown[symbol] = time.time()
        return True

    def check_prices(self):
        """Poll all watchlist stocks and detect threshold crossings."""
        if self._should_skip_check():
            return

        with self._lock:
            for stock in self.watchlist:
                symbol = stock.get("symbol", "")
                threshold = stock.get("alert_threshold", 3.0)

                try:
                    data = get_stock_price(symbol)
                    if "error" in data:
                        continue

                    price = data["price"]
                    change_pct = data["change_pct"]
                    timestamp = time.time()

                    # Store in history
                    if symbol not in self.price_history:
                        self.price_history[symbol] = []
                    self.price_history[symbol].append((timestamp, price))

                    # Keep only last 100 data points per symbol
                    if len(self.price_history[symbol]) > 100:
                        self.price_history[symbol] = self.price_history[symbol][-100:]

                    # Check for alert
                    self._detect_alert(symbol, price, change_pct, threshold)

                except Exception as e:
                    print(f"[StockMonitor] Error checking {symbol}: {e}")

    def _monitor_loop(self):
        """Background monitoring loop."""
        print("[StockMonitor] Starting monitoring loop")

        while self.running:
            try:
                self.check_prices()
                interval = self.alert_settings.get("check_interval_minutes", 15)
                time.sleep(interval * 60)
            except Exception as e:
                print(f"[StockMonitor] Monitor loop error: {e}")
                time.sleep(60)  # Wait 1 min before retry

        print("[StockMonitor] Monitoring loop stopped")

    def start(self):
        """Start the background monitoring thread."""
        if self.running:
            print("[StockMonitor] Already running")
            return

        if not self._load_watchlist():
            print("[StockMonitor] Failed to start — watchlist load failed")
            return

        if not self.alert_settings.get("voice_alerts", True):
            print("[StockMonitor] Voice alerts disabled in settings")
            return

        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        print("[StockMonitor] Started successfully")

    def stop(self):
        """Stop the monitoring thread."""
        if not self.running:
            return

        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("[StockMonitor] Stopped")

    def get_watchlist_summary(self) -> str:
        """Get current watchlist with live prices (on-demand query)."""
        if not self._load_watchlist():
            return "Watchlist unavailable."

        lines = ["Stock Watchlist:"]
        for stock in self.watchlist:
            symbol = stock.get("symbol", "")
            threshold = stock.get("alert_threshold", 0)
            data = get_stock_price(symbol)

            if "error" not in data:
                price = data["price"]
                change = data["change_pct"]
                direction = "↑" if change >= 0 else "↓"
                lines.append(f"{symbol}: ${price:,.2f} ({direction}{abs(change):.2f}%)")
            else:
                lines.append(f"{symbol}: Price unavailable")

        return "\n".join(lines)


# Singleton instance for global access
_monitor_instance: Optional[StockMonitor] = None


def get_monitor() -> StockMonitor:
    """Get or create the global StockMonitor instance."""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = StockMonitor()
    return _monitor_instance


if __name__ == "__main__":
    # Test the monitor
    monitor = StockMonitor()
    monitor._load_watchlist()
    print(monitor.get_watchlist_summary())
    print("\nChecking prices once...")
    monitor.check_prices()
