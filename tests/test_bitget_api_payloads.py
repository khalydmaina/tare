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


def test_keys_alone_do_not_route_fills_to_the_exchange():
    """Fills follow execution.fills, not whether the keys happen to be set.

    The demo exchange filled a test order 3% away from the public market and does not list
    every watchlist symbol, so routing there has to be asked for, never inherited.
    """
    broker = PaperBroker(api_key="k", api_secret="s", passphrase="p")
    assert broker.fills == "sim"
    assert broker._has_keys and not broker._use_api

    routed = PaperBroker(api_key="k", api_secret="s", passphrase="p", fills="bitget-demo")
    assert routed._use_api


def test_a_refused_order_says_so_instead_of_passing_as_an_exchange_fill(monkeypatch):
    broker = PaperBroker(api_key="k", api_secret="s", passphrase="p", fills="bitget-demo")

    def refuse(*_a, **_k):
        raise RuntimeError("Bitget rejected /api/v2/mix/order/place-order: 22016 stop loss price")

    monkeypatch.setattr(broker, "_place_api_order", refuse)
    order = broker.place_order("LTCUSDT", Side.SHORT, 10.0, 54.0, 54.2, 53.5, last_price=54.0)

    assert order["mode"] == "sim"
    assert order["exchange_order_id"] is None
    assert "22016" in order["api_error"]
    assert broker.api_failures and broker.api_failures[0]["symbol"] == "LTCUSDT"


def test_bitget_error_carries_the_reason_from_the_response_body():
    import httpx

    from execution.bitget_broker import BitgetError, _raise_for_body

    response = httpx.Response(
        400,
        json={"code": "40034", "msg": "Parameter WLDUSDT does not exist"},
        request=httpx.Request("POST", "https://api.bitget.com/api/v2/mix/order/place-order"),
    )
    try:
        _raise_for_body(response, "/api/v2/mix/order/place-order")
    except BitgetError as exc:
        assert exc.code == "40034"
        assert "does not exist" in exc.msg
        assert "40034" in str(exc)
    else:
        raise AssertionError("a 400 must raise")
