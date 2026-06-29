from realtime_alpha.cli import build_parser


def test_serve_parser_defaults():
    args = build_parser().parse_args(["serve"])
    assert args.command == "serve"
    assert args.host == "127.0.0.1"
    assert args.port == 8000
    assert args.source is None


def test_serve_parser_overrides():
    args = build_parser().parse_args(["serve", "--host", "0.0.0.0", "--port", "9001", "--source", "ws"])
    assert args.host == "0.0.0.0"
    assert args.port == 9001
    assert args.source == "ws"


def test_sentiment_parser_defaults():
    args = build_parser().parse_args(["sentiment"])
    assert args.command == "sentiment"
    assert args.symbols == "BTCUSDT,ETHUSDT"
    assert args.interval == 45.0
    assert args.once is False


def test_deep_parser_defaults():
    args = build_parser().parse_args(["deep"])
    assert args.command == "deep"
    assert args.symbols == "BTCUSDT,ETHUSDT"
    assert args.once is False
