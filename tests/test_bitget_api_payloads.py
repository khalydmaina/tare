"""Requests the demo API receives, checked without the network."""

from types import SimpleNamespace

from execution.bitget_broker import PaperBroker, Side


def test_api_close_sends_size_at_contract_precision(monkeypatch):
    broker = PaperBroker(api_key="k", api_secret="s", passphrase="p")
    broker._specs["DOGEUSDT"] = {"volume_place": 0, "price_place": 5, "size_multiplier": 1, "min_trade_num": 1}
    sent: dict = {}
    monkeypatch.setattr(broker, "_post", lambda path, payload: sent.update(payload) or {"orderId": ""})

    pos = SimpleNamespace(symbol="DOGEUSDT", side=Side.LONG, size=44.0, fill_price=0.2)
    assert broker._close_api_position(pos) == 0.2
    assert sent["size"] == "44"
    # Hedge mode: the side names the position being closed (verified on the demo exchange)
    assert (sent["side"], sent["tradeSide"]) == ("buy", "close")


def test_demo_requests_carry_the_paper_trading_header():
    broker = PaperBroker(api_key="k", api_secret="s", passphrase="p")
    headers = broker._headers("GET", "/api/v2/mix/account/accounts?productType=USDT-FUTURES")
    assert headers["paptrading"] == "1"
    assert headers["ACCESS-KEY"] == "k" and headers["ACCESS-PASSPHRASE"] == "p"
