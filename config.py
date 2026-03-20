"""
config.py — RWA Infinity Model v1.0
Complete Real World Asset universe, risk tiers, API config.
"""

import os as _os

# ─────────────────────────────────────────────────────────────────────────────
# API KEYS  (read from environment variables — set in .env or shell before launch)
# To activate a key: export RWA_COINGECKO_API_KEY="your_key_here"
# All keys default to None; the app degrades gracefully to free-tier endpoints.
# ─────────────────────────────────────────────────────────────────────────────

# ── Price & Market Data ──────────────────────────────────────────────────────
COINGECKO_API_KEY       = _os.environ.get("RWA_COINGECKO_API_KEY")       # CoinGecko Pro / Demo
COINMARKETCAP_API_KEY   = _os.environ.get("RWA_COINMARKETCAP_API_KEY")   # coinmarketcap.com
TIINGO_API_KEY          = _os.environ.get("RWA_TIINGO_API_KEY")          # tiingo.com — stocks/ETFs/crypto
ALPHA_VANTAGE_API_KEY   = _os.environ.get("RWA_ALPHA_VANTAGE_API_KEY")   # alphavantage.co — stocks/forex
FRED_API_KEY            = _os.environ.get("RWA_FRED_API_KEY")            # fred.stlouisfed.org — macro/rates
MESSARI_API_KEY         = _os.environ.get("RWA_MESSARI_API_KEY")         # messari.io — crypto fundamentals
NANSEN_API_KEY          = _os.environ.get("RWA_NANSEN_API_KEY")          # nansen.ai — on-chain analytics
DUNE_API_KEY            = _os.environ.get("RWA_DUNE_API_KEY")            # dune.com — on-chain analytics
MORALIS_API_KEY         = _os.environ.get("RWA_MORALIS_API_KEY")         # moralis.io — cross-chain data
KAIKO_API_KEY           = _os.environ.get("RWA_KAIKO_API_KEY")           # kaiko.com — institutional market data
COIN_METRICS_API_KEY    = _os.environ.get("RWA_COIN_METRICS_API_KEY")    # coinmetrics.io — network data

# ── Block Explorers ──────────────────────────────────────────────────────────
ETHERSCAN_API_KEY       = _os.environ.get("RWA_ETHERSCAN_API_KEY")       # etherscan.io
POLYGONSCAN_API_KEY     = _os.environ.get("RWA_POLYGONSCAN_API_KEY")     # polygonscan.com
ARBISCAN_API_KEY        = _os.environ.get("RWA_ARBISCAN_API_KEY")        # arbiscan.io — Arbitrum
BSCSCAN_API_KEY         = _os.environ.get("RWA_BSCSCAN_API_KEY")         # bscscan.com — BNB Chain
OPTIMISTIC_API_KEY      = _os.environ.get("RWA_OPTIMISTIC_API_KEY")      # optimistic.etherscan.io
BASESCAN_API_KEY        = _os.environ.get("RWA_BASESCAN_API_KEY")        # basescan.org — Base
SNOWTRACE_API_KEY       = _os.environ.get("RWA_SNOWTRACE_API_KEY")       # snowtrace.io — Avalanche
SOLSCAN_API_KEY         = _os.environ.get("RWA_SOLSCAN_API_KEY")         # solscan.io — Solana

# ── Web3 Node Providers ──────────────────────────────────────────────────────
ALCHEMY_API_KEY         = _os.environ.get("RWA_ALCHEMY_API_KEY")         # alchemy.com — Ethereum/Polygon/etc.
INFURA_API_KEY          = _os.environ.get("RWA_INFURA_API_KEY")          # infura.io — Ethereum/IPFS
HELIUS_API_KEY          = _os.environ.get("RWA_HELIUS_API_KEY")          # helius.dev — Solana RPC
QUICKNODE_API_KEY       = _os.environ.get("RWA_QUICKNODE_API_KEY")       # quicknode.com — multi-chain RPC
THE_GRAPH_API_KEY       = _os.environ.get("RWA_THE_GRAPH_API_KEY")       # thegraph.com — DeFi subgraphs

# ── CEX Trading APIs ─────────────────────────────────────────────────────────
BINANCE_API_KEY         = _os.environ.get("RWA_BINANCE_API_KEY")         # binance.com (read-only)
BINANCE_API_SECRET      = _os.environ.get("RWA_BINANCE_API_SECRET")
COINBASE_API_KEY        = _os.environ.get("RWA_COINBASE_API_KEY")        # advanced trade API
COINBASE_API_SECRET     = _os.environ.get("RWA_COINBASE_API_SECRET")
KRAKEN_API_KEY          = _os.environ.get("RWA_KRAKEN_API_KEY")
KRAKEN_API_SECRET       = _os.environ.get("RWA_KRAKEN_API_SECRET")
OKX_API_KEY             = _os.environ.get("RWA_OKX_API_KEY")
OKX_API_SECRET          = _os.environ.get("RWA_OKX_API_SECRET")
BYBIT_API_KEY           = _os.environ.get("RWA_BYBIT_API_KEY")
BYBIT_API_SECRET        = _os.environ.get("RWA_BYBIT_API_SECRET")
KUCOIN_API_KEY          = _os.environ.get("RWA_KUCOIN_API_KEY")
KUCOIN_API_SECRET       = _os.environ.get("RWA_KUCOIN_API_SECRET")
KUCOIN_API_PASSPHRASE   = _os.environ.get("RWA_KUCOIN_API_PASSPHRASE")
GATE_IO_API_KEY         = _os.environ.get("RWA_GATE_IO_API_KEY")
GATE_IO_API_SECRET      = _os.environ.get("RWA_GATE_IO_API_SECRET")
DERIBIT_API_KEY         = _os.environ.get("RWA_DERIBIT_API_KEY")        # deribit.com — options/futures
DERIBIT_API_SECRET      = _os.environ.get("RWA_DERIBIT_API_SECRET")

# ── DEX / DeFi Data ──────────────────────────────────────────────────────────
DYDX_API_KEY            = _os.environ.get("RWA_DYDX_API_KEY")           # dydx.exchange
DYDX_API_SECRET         = _os.environ.get("RWA_DYDX_API_SECRET")
DYDX_PASSPHRASE         = _os.environ.get("RWA_DYDX_PASSPHRASE")
PARASWAP_API_KEY        = _os.environ.get("RWA_PARASWAP_API_KEY")       # paraswap.io DEX aggregator
ONEINCH_API_KEY         = _os.environ.get("RWA_ONEINCH_API_KEY")        # 1inch.io DEX aggregator
ZERO_EX_API_KEY         = _os.environ.get("RWA_ZERO_EX_API_KEY")        # 0x.org DEX protocol

# ── RWA-Specific Platform APIs ───────────────────────────────────────────────
SECURITIZE_API_KEY      = _os.environ.get("RWA_SECURITIZE_API_KEY")     # securitize.io — BUIDL issuer
CENTRIFUGE_API_KEY      = _os.environ.get("RWA_CENTRIFUGE_API_KEY")     # centrifuge.io — private credit
MAPLE_API_KEY           = _os.environ.get("RWA_MAPLE_API_KEY")          # maple.finance
GOLDFINCH_API_KEY       = _os.environ.get("RWA_GOLDFINCH_API_KEY")      # goldfinch.finance
CREDIX_API_KEY          = _os.environ.get("RWA_CREDIX_API_KEY")         # credix.finance
ONDO_API_KEY            = _os.environ.get("RWA_ONDO_API_KEY")           # ondo.finance
PENDLE_API_KEY          = _os.environ.get("RWA_PENDLE_API_KEY")         # pendle.finance
SUPERSTATE_API_KEY      = _os.environ.get("RWA_SUPERSTATE_API_KEY")     # superstate.co
BACKED_API_KEY          = _os.environ.get("RWA_BACKED_API_KEY")         # backed.fi — tokenized ETFs
DINARI_API_KEY          = _os.environ.get("RWA_DINARI_API_KEY")         # dinari.com — dShares
OPENEDEN_API_KEY        = _os.environ.get("RWA_OPENEDEN_API_KEY")       # openeden.com — TBILL (Moody's A)
MATRIXDOCK_API_KEY      = _os.environ.get("RWA_MATRIXDOCK_API_KEY")     # matrixdock.com — STBT/XAUm
HASHNOTE_API_KEY        = _os.environ.get("RWA_HASHNOTE_API_KEY")       # hashnote.com — USYC
SPIKO_API_KEY           = _os.environ.get("RWA_SPIKO_API_KEY")          # spiko.io — Euro T-bill fund
LOFTY_API_KEY           = _os.environ.get("RWA_LOFTY_API_KEY")          # lofty.ai — tokenized RE
REALT_API_KEY           = _os.environ.get("RWA_REALT_API_KEY")          # realt.co — tokenized RE
PROPY_API_KEY           = _os.environ.get("RWA_PROPY_API_KEY")          # propy.com — RE title/escrow
MANTRA_API_KEY          = _os.environ.get("RWA_MANTRA_API_KEY")         # mantrachain.io
PLUME_API_KEY           = _os.environ.get("RWA_PLUME_API_KEY")          # plumenetwork.xyz

# ── News & Sentiment ─────────────────────────────────────────────────────────
NEWSAPI_API_KEY         = _os.environ.get("RWA_NEWSAPI_API_KEY")        # newsapi.org
CRYPTOPANIC_API_KEY     = _os.environ.get("RWA_CRYPTOPANIC_API_KEY")    # cryptopanic.com
TWITTER_BEARER_TOKEN    = _os.environ.get("RWA_TWITTER_BEARER_TOKEN")   # Twitter/X v2 API
REDDIT_CLIENT_ID        = _os.environ.get("RWA_REDDIT_CLIENT_ID")       # Reddit API
REDDIT_CLIENT_SECRET    = _os.environ.get("RWA_REDDIT_CLIENT_SECRET")
LUNARCRUSH_API_KEY      = _os.environ.get("RWA_LUNARCRUSH_API_KEY")     # lunarcrush.com — social analytics
SANTIMENT_API_KEY       = _os.environ.get("RWA_SANTIMENT_API_KEY")      # santiment.net — on-chain/social

# ── Notifications ────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN      = _os.environ.get("RWA_TELEGRAM_BOT_TOKEN")     # Telegram bot notifications
TELEGRAM_CHAT_ID        = _os.environ.get("RWA_TELEGRAM_CHAT_ID")       # Target chat/channel ID
DISCORD_WEBHOOK_URL     = _os.environ.get("RWA_DISCORD_WEBHOOK_URL")    # Discord webhook URL
SMTP_HOST               = _os.environ.get("RWA_SMTP_HOST", "smtp.gmail.com")
try:
    SMTP_PORT           = int(_os.environ.get("RWA_SMTP_PORT", "587"))
except (ValueError, TypeError):
    SMTP_PORT           = 587
SMTP_USER               = _os.environ.get("RWA_SMTP_USER")
SMTP_PASSWORD           = _os.environ.get("RWA_SMTP_PASSWORD")
ALERT_EMAIL             = _os.environ.get("RWA_ALERT_EMAIL")            # Destination email for alerts

# ─────────────────────────────────────────────────────────────────────────────
# API ENDPOINTS  (upgrade to pro when key is present)
# ─────────────────────────────────────────────────────────────────────────────

DEFILLAMA_BASE      = "https://api.llama.fi"
DEFILLAMA_YIELDS    = "https://yields.llama.fi"

# CoinGecko: use Pro endpoint when key available (higher rate limits + extra data)
COINGECKO_BASE      = (
    "https://pro-api.coingecko.com/api/v3"
    if COINGECKO_API_KEY else
    "https://api.coingecko.com/api/v3"
)

RWA_XYZ_BASE        = "https://app.rwa.xyz"          # scrape / public data
ETHERSCAN_BASE      = "https://api.etherscan.io/api"
POLYGONSCAN_BASE    = "https://api.polygonscan.com/api"
ARBISCAN_BASE       = "https://api.arbiscan.io/api"
BSCSCAN_BASE        = "https://api.bscscan.com/api"
BASESCAN_BASE       = "https://api.basescan.org/api"
SNOWTRACE_BASE      = "https://api.snowtrace.io/api"

# CEX Public Market Data (read-only, no auth needed for prices)
BINANCE_BASE        = "https://api.binance.com/api/v3"
COINBASE_BASE       = "https://api.coinbase.com/v2"
KRAKEN_BASE         = "https://api.kraken.com/0/public"
OKX_BASE            = "https://www.okx.com/api/v5"
BYBIT_BASE          = "https://api.bybit.com/v5"
KUCOIN_BASE         = "https://api.kucoin.com/api/v1"
GATE_IO_BASE        = "https://api.gateio.ws/api/v4"

# CoinMarketCap (requires key)
COINMARKETCAP_BASE  = "https://pro-api.coinmarketcap.com/v1"

# FRED (Federal Reserve — free with key, higher limits)
FRED_BASE           = "https://api.stlouisfed.org/fred"

# Tiingo (requires key — stocks, ETFs, crypto prices)
TIINGO_BASE         = "https://api.tiingo.com"

# Alpha Vantage (requires key — stocks, forex, commodities)
ALPHA_VANTAGE_BASE  = "https://www.alphavantage.co/query"

# Messari (requires key for extended data)
MESSARI_BASE        = "https://data.messari.io/api/v1"

# News APIs
NEWSAPI_BASE        = "https://newsapi.org/v2"
CRYPTOPANIC_BASE    = "https://cryptopanic.com/api/v1"

# ─── HTTP Config ───────────────────────────────────────────────────────────────
REQUEST_TIMEOUT     = 15   # seconds
MAX_RETRIES         = 3
RETRY_BACKOFF       = 1.5  # exponential back-off multiplier

# ─── Scheduler ────────────────────────────────────────────────────────────────
REFRESH_INTERVAL_MINUTES = 60   # full data refresh every hour
PRICE_INTERVAL_SECONDS   = 300  # price-only refresh every 5 min
NEWS_INTERVAL_MINUTES    = 30   # news sentiment refresh

# ─── Database ─────────────────────────────────────────────────────────────────
DB_FILE = "rwa_model.db"

# ─── Anthropic ────────────────────────────────────────────────────────────────
CLAUDE_MODEL    = "claude-sonnet-4-6"
CLAUDE_TIMEOUT  = 45.0
AI_CACHE_TTL    = 1800   # 30 min

# ─────────────────────────────────────────────────────────────────────────────
# COMPLETE RWA ASSET UNIVERSE
# Each asset: id, name, category, subcategory, chain, protocol, token_symbol,
#             coingecko_id, defillama_slug, expected_yield_pct, risk_score (1-10),
#             liquidity_score (1-10), regulatory_score (1-10), description
# ─────────────────────────────────────────────────────────────────────────────

RWA_UNIVERSE = [

    # ── TOKENIZED US TREASURIES & GOVERNMENT BONDS ──────────────────────────
    {
        "id": "BUIDL",
        "name": "BlackRock USD Institutional Digital Liquidity Fund",
        "category": "Government Bonds",
        "subcategory": "US Treasury",
        "chain": "Ethereum",
        "protocol": "BlackRock / Securitize",
        "token_symbol": "BUIDL",
        "coingecko_id": None,
        "defillama_slug": "blackrock-buidl",
        "expected_yield_pct": 4.450,
        "risk_score": 1,
        "liquidity_score": 7,
        "regulatory_score": 10,
        "min_investment_usd": 5_000_000,
        "inception_date": "2024-03-20",
        "description": "BlackRock's tokenized money market fund backed by US Treasury bills. Institutional grade, $100+ billion AUM manager.",
        "tags": ["institutional", "treasury", "money-market", "accredited"],
    },
    {
        "id": "BENJI",
        "name": "Franklin OnChain US Government Money Fund",
        "category": "Government Bonds",
        "subcategory": "US Treasury",
        "chain": "Stellar / Polygon",
        "protocol": "Franklin Templeton",
        "token_symbol": "BENJI",
        "coingecko_id": None,
        "defillama_slug": "franklin-benji",
        "expected_yield_pct": 4.4,
        "risk_score": 1,
        "liquidity_score": 8,
        "regulatory_score": 10,
        "min_investment_usd": 0,
        "inception_date": "2021-04-04",
        "description": "First US-registered fund to use public blockchain for transaction processing. US govt securities + overnight repos.",
        "tags": ["retail", "treasury", "money-market", "registered-fund"],
    },
    {
        "id": "USTB",
        "name": "Superstate Short Duration US Government Securities Fund",
        "category": "Government Bonds",
        "subcategory": "US Treasury",
        "chain": "Ethereum",
        "protocol": "Superstate",
        "token_symbol": "USTB",
        "coingecko_id": "superstate-short-duration-us-government-securities-fund",
        "defillama_slug": "superstate",
        "expected_yield_pct": 4.43,
        "risk_score": 1,
        "liquidity_score": 8,
        "regulatory_score": 9,
        "min_investment_usd": 100_000,
        "inception_date": "2023-08-01",
        "description": "SEC-registered 40-Act fund tokenized on Ethereum. Direct competitor to BUIDL with broader access.",
        "tags": ["institutional", "treasury", "registered-fund", "sec"],
    },
    {
        "id": "TBILL",
        "name": "OpenEden T-Bill Vault",
        "category": "Government Bonds",
        "subcategory": "US Treasury",
        "chain": "Ethereum",
        "protocol": "OpenEden",
        "token_symbol": "TBILL",
        "coingecko_id": "openeden-tbill",
        "defillama_slug": "openeden",
        "expected_yield_pct": 4.47,
        "risk_score": 2,
        "liquidity_score": 9,
        "regulatory_score": 8,
        "min_investment_usd": 100_000,
        "inception_date": "2023-01-10",
        "description": "24/7 T-bill yield vault with daily liquidity. Licensed in Singapore, backed by US short-duration Treasuries.",
        "tags": ["institutional", "treasury", "defi-native", "singapore"],
    },
    {
        "id": "OUSG",
        "name": "Ondo Short-Term US Government Bond Fund",
        "category": "Government Bonds",
        "subcategory": "US Treasury",
        "chain": "Ethereum / Polygon / Solana",
        "protocol": "Ondo Finance",
        "token_symbol": "OUSG",
        "coingecko_id": "ondo-us-dollar-yield",
        "defillama_slug": "ondo-finance",
        "expected_yield_pct": 4.37,
        "risk_score": 2,
        "liquidity_score": 9,
        "regulatory_score": 9,
        "min_investment_usd": 100_000,
        "inception_date": "2023-01-04",
        "description": "Tokenized BlackRock iShares Short Treasury Bond ETF. Multi-chain, daily NAV updates, KYC required.",
        "tags": ["institutional", "treasury", "multi-chain", "accredited"],
    },
    {
        "id": "OMMF",
        "name": "Ondo US Money Market Fund",
        "category": "Government Bonds",
        "subcategory": "Money Market",
        "chain": "Ethereum",
        "protocol": "Ondo Finance",
        "token_symbol": "OMMF",
        "coingecko_id": None,
        "defillama_slug": "ondo-finance",
        "expected_yield_pct": 4.3,
        "risk_score": 1,
        "liquidity_score": 9,
        "regulatory_score": 9,
        "min_investment_usd": 100_000,
        "inception_date": "2023-06-01",
        "description": "Tokenized US money market fund. Holds overnight repos and T-bills. 1:1 USD redeemable.",
        "tags": ["institutional", "money-market", "accredited"],
    },
    {
        "id": "USDM",
        "name": "Mountain Protocol USD",
        "category": "Government Bonds",
        "subcategory": "Yield Stablecoin",
        "chain": "Ethereum / Polygon",
        "protocol": "Mountain Protocol",
        "token_symbol": "USDM",
        "coingecko_id": "usdm",
        "defillama_slug": "mountain-protocol",
        "expected_yield_pct": 4.250,
        "risk_score": 2,
        "liquidity_score": 10,
        "regulatory_score": 8,
        "min_investment_usd": 1,
        "inception_date": "2023-09-01",
        "description": "Yield-bearing stablecoin backed by T-bills. Rebasing token — balance grows daily. Bermuda-regulated.",
        "tags": ["retail", "stablecoin", "treasury", "yield-bearing", "rebasing"],
    },
    {
        "id": "USDY",
        "name": "Ondo US Dollar Yield Token",
        "category": "Government Bonds",
        "subcategory": "Yield Stablecoin",
        "chain": "Ethereum / Solana / Mantle",
        "protocol": "Ondo Finance",
        "token_symbol": "USDY",
        "coingecko_id": "ondo-us-dollar-yield-token",
        "defillama_slug": "ondo-finance",
        "expected_yield_pct": 4.350,
        "risk_score": 2,
        "liquidity_score": 10,
        "regulatory_score": 8,
        "min_investment_usd": 500,
        "inception_date": "2023-08-01",
        "description": "Tokenized note backed by US bank demand deposits and Treasuries. Transferable after 40-day lockup.",
        "tags": ["retail", "stablecoin", "treasury", "yield-bearing"],
    },
    {
        "id": "STBT",
        "name": "Matrixdock Short-Term Treasury Bill Token",
        "category": "Government Bonds",
        "subcategory": "US Treasury",
        "chain": "Ethereum",
        "protocol": "Matrixdock",
        "token_symbol": "STBT",
        "coingecko_id": "stbt",
        "defillama_slug": "matrixdock-stbt",
        "expected_yield_pct": 4.2,
        "risk_score": 2,
        "liquidity_score": 7,
        "regulatory_score": 7,
        "min_investment_usd": 100_000,
        "inception_date": "2023-03-01",
        "description": "First Asian tokenized short-term T-bill by Matrixdock (Matrixport). Rebases daily to distribute yield. Used as DeFi collateral on Curve. Expanding to precious metals (silver, platinum, palladium) in 2025.",
        "tags": ["institutional", "treasury", "defi-collateral", "matrixdock", "asian-market", "rebasing"],
    },

    {
        "id": "MTBILL",
        "name": "Midas mTBILL — Tokenized US T-Bill",
        "category": "Government Bonds",
        "subcategory": "US Treasury",
        "chain": "Ethereum / Base",
        "protocol": "Midas",
        "token_symbol": "mTBILL",
        "coingecko_id": "midas-mtbill",
        "defillama_slug": "midas-mtbill",
        "expected_yield_pct": 4.48,
        "risk_score": 2,
        "liquidity_score": 8,
        "regulatory_score": 8,
        "min_investment_usd": 100_000,
        "inception_date": "2023-11-01",
        "tvl_usd": 400_000_000,
        "description": "Midas tokenized US T-bill fund (~$400M TVL). ERC-20 yield token backed by short-duration US Treasuries. MiCA-compliant, deployed on Ethereum and Base. Redeemable T+1.",
        "tags": ["institutional", "treasury", "midas", "mica-compliant", "multi-chain"],
    },
    {
        "id": "MBASIS",
        "name": "Midas mBASIS — Tokenized Basis Trade",
        "category": "Government Bonds",
        "subcategory": "Basis Trade",
        "chain": "Ethereum / Base",
        "protocol": "Midas",
        "token_symbol": "mBASIS",
        "coingecko_id": "midas-mbasis",
        "defillama_slug": "midas-mbasis",
        "expected_yield_pct": 15.0,
        "risk_score": 5,
        "liquidity_score": 7,
        "regulatory_score": 7,
        "min_investment_usd": 100_000,
        "inception_date": "2024-03-01",
        "tvl_usd": 50_000_000,
        "description": "Midas tokenized basis trade — captures the funding rate spread between spot BTC/ETH and perpetual futures. Higher yield than T-bills with moderate market risk. MiCA-compliant EU issuance.",
        "tags": ["institutional", "basis-trade", "midas", "mica-compliant", "funding-rate"],
    },

    # ── PRIVATE CREDIT / DEBT ────────────────────────────────────────────────
    {
        "id": "MAPLE_USDC",
        "name": "Maple Finance Cash Management Pool",
        "category": "Private Credit",
        "subcategory": "Cash Management",
        "chain": "Ethereum / Solana",
        "protocol": "Maple Finance",
        "token_symbol": "MPL",
        "coingecko_id": "maple",
        "defillama_slug": "maple",
        "expected_yield_pct": 8.50,
        "risk_score": 4,
        "liquidity_score": 7,
        "regulatory_score": 7,
        "min_investment_usd": 50_000,
        "inception_date": "2021-06-01",
        "description": "Institutional lending pools for accredited borrowers. Senior secured, overcollateralized positions.",
        "tags": ["institutional", "private-credit", "lending", "accredited"],
    },
    {
        "id": "MAPLE_HIGH_YIELD",
        "name": "Maple Finance High Yield Secured Lending",
        "category": "Private Credit",
        "subcategory": "High Yield",
        "chain": "Ethereum",
        "protocol": "Maple Finance",
        "token_symbol": "MPL",
        "coingecko_id": "maple",
        "defillama_slug": "maple",
        "expected_yield_pct": 12.50,
        "risk_score": 6,
        "liquidity_score": 5,
        "regulatory_score": 7,
        "min_investment_usd": 100_000,
        "inception_date": "2022-01-01",
        "description": "Higher-yield pools targeting emerging market borrowers and growth-stage crypto companies.",
        "tags": ["institutional", "high-yield", "private-credit", "accredited"],
    },
    {
        "id": "GFI_SENIOR",
        "name": "Goldfinch Senior Pool",
        "category": "Private Credit",
        "subcategory": "Emerging Market Loans",
        "chain": "Ethereum",
        "protocol": "Goldfinch",
        "token_symbol": "GFI",
        "coingecko_id": "goldfinch",
        "defillama_slug": "goldfinch",
        "expected_yield_pct": 8.00,
        "risk_score": 5,
        "liquidity_score": 6,
        "regulatory_score": 7,
        "min_investment_usd": 0,
        "inception_date": "2021-01-01",
        "description": "Automated senior pool lending to emerging market borrowers (India, SE Asia, Africa). Auto-diversified.",
        "tags": ["retail", "private-credit", "emerging-markets", "senior"],
    },
    {
        "id": "GFI_TRANCHED",
        "name": "Goldfinch Tranched Pools",
        "category": "Private Credit",
        "subcategory": "Emerging Market Loans",
        "chain": "Ethereum",
        "protocol": "Goldfinch",
        "token_symbol": "GFI",
        "coingecko_id": "goldfinch",
        "defillama_slug": "goldfinch",
        "expected_yield_pct": 14.00,
        "risk_score": 7,
        "liquidity_score": 4,
        "regulatory_score": 6,
        "min_investment_usd": 0,
        "inception_date": "2021-06-01",
        "description": "Junior tranche pools with higher yield. Absorbs first-loss risk from senior pool capital.",
        "tags": ["retail", "private-credit", "emerging-markets", "junior", "high-yield"],
    },
    {
        "id": "TRUEFI_SECURED",
        "name": "TrueFi Secured Lending",
        "category": "Private Credit",
        "subcategory": "Secured Loans",
        "chain": "Ethereum / Optimism",
        "protocol": "TrueFi",
        "token_symbol": "TRU",
        "coingecko_id": "truefi",
        "defillama_slug": "truefi",
        "expected_yield_pct": 9.50,
        "risk_score": 5,
        "liquidity_score": 6,
        "regulatory_score": 7,
        "min_investment_usd": 0,
        "inception_date": "2020-11-01",
        "description": "On-chain credit rating system for institutional borrowers. Community-voted credit decisions.",
        "tags": ["institutional", "private-credit", "secured", "credit-scoring"],
    },
    {
        "id": "CFG_TINLAKE",
        "name": "Centrifuge Tinlake Asset Pools",
        "category": "Private Credit",
        "subcategory": "Trade Finance / Invoices",
        "chain": "Ethereum / Centrifuge Chain",
        "protocol": "Centrifuge",
        "token_symbol": "CFG",
        "coingecko_id": "centrifuge",
        "defillama_slug": "centrifuge",
        "expected_yield_pct": 10.50,
        "risk_score": 5,
        "liquidity_score": 5,
        "regulatory_score": 7,
        "min_investment_usd": 0,
        "inception_date": "2021-05-01",
        "description": "NFT-backed real-world loan pools. Asset types: freight invoices, US real estate bridge loans, consumer credit.",
        "tags": ["retail", "private-credit", "trade-finance", "invoices", "nft"],
    },
    {
        "id": "ARCA_DIGITAL",
        "name": "Arca US Treasury Fund",
        "category": "Private Credit",
        "subcategory": "Treasury + Credit",
        "chain": "Ethereum",
        "protocol": "Arca",
        "token_symbol": "ArCoin",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 5.50,
        "risk_score": 3,
        "liquidity_score": 6,
        "regulatory_score": 9,
        "min_investment_usd": 1_000,
        "inception_date": "2020-07-01",
        "description": "SEC-registered digital fund combining US Treasuries with a small credit allocation. Daily NAV.",
        "tags": ["institutional", "treasury", "credit-blend", "registered-fund"],
    },

    # ── REAL ESTATE ──────────────────────────────────────────────────────────
    {
        "id": "REALT_RES",
        "name": "RealT Residential Rental Properties",
        "category": "Real Estate",
        "subcategory": "Residential Rental",
        "chain": "Ethereum / Gnosis",
        "protocol": "RealT",
        "token_symbol": "REALT",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 8.50,
        "risk_score": 5,
        "liquidity_score": 4,
        "regulatory_score": 7,
        "min_investment_usd": 50,
        "inception_date": "2019-10-01",
        "description": "Fractional US residential real estate. Rental income paid weekly in xDAI. Properties in Detroit, Chicago, Cleveland.",
        "tags": ["retail", "real-estate", "residential", "rental-income", "fractional"],
    },
    {
        "id": "LOFTY_RES",
        "name": "Lofty.ai Tokenized Rental Properties",
        "category": "Real Estate",
        "subcategory": "Residential Rental",
        "chain": "Algorand",
        "protocol": "Lofty.ai",
        "token_symbol": "LOFTY",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 7.50,
        "risk_score": 5,
        "liquidity_score": 5,
        "regulatory_score": 8,
        "min_investment_usd": 50,
        "inception_date": "2021-04-01",
        "description": "Algorand-based fractional real estate. 100+ US properties, daily rent payouts, secondary market trading.",
        "tags": ["retail", "real-estate", "residential", "rental-income", "algorand"],
    },
    {
        "id": "TANGIBLE_USDR",
        "name": "Tangible USDR - Real Estate Stablecoin",
        "category": "Real Estate",
        "subcategory": "Real Estate Stablecoin",
        "chain": "Polygon",
        "protocol": "Tangible",
        "token_symbol": "USDR",
        "coingecko_id": "real-usd",
        "defillama_slug": "tangible",
        "expected_yield_pct": 8.00,
        "risk_score": 6,
        "liquidity_score": 7,
        "regulatory_score": 6,
        "min_investment_usd": 1,
        "inception_date": "2022-10-01",
        "description": "Stablecoin backed by tokenized UK real estate + TNGBL token insurance fund. Yield from rental income.",
        "tags": ["retail", "real-estate", "stablecoin", "yield-bearing", "uk"],
    },
    {
        "id": "PARCL",
        "name": "Parcl Real Estate Index",
        "category": "Real Estate",
        "subcategory": "Real Estate Index",
        "chain": "Solana",
        "protocol": "Parcl",
        "token_symbol": "PARCL",
        "coingecko_id": "parcl",
        "defillama_slug": "parcl",
        "expected_yield_pct": 12.00,
        "risk_score": 7,
        "liquidity_score": 8,
        "regulatory_score": 6,
        "min_investment_usd": 10,
        "inception_date": "2023-03-01",
        "description": "Synthetic real estate indices on Solana. Go long/short on NYC, Miami, LA, SF real estate price indices.",
        "tags": ["retail", "real-estate", "synthetic", "index", "leverage"],
    },
    {
        "id": "PROPY",
        "name": "Propy Real Estate NFT Titles",
        "category": "Real Estate",
        "subcategory": "Title / Deed NFT",
        "chain": "Ethereum / Polygon",
        "protocol": "Propy",
        "token_symbol": "PRO",
        "coingecko_id": "propy",
        "defillama_slug": None,
        "expected_yield_pct": 6.00,
        "risk_score": 6,
        "liquidity_score": 4,
        "regulatory_score": 8,
        "min_investment_usd": 1_000,
        "inception_date": "2017-01-01",
        "description": "Blockchain property titles and real estate NFT marketplace. US + international properties.",
        "tags": ["retail", "real-estate", "title-nft", "marketplace"],
    },
    {
        "id": "LANDSHARES",
        "name": "Landshares Farmland Tokens",
        "category": "Real Estate",
        "subcategory": "Agricultural Land",
        "chain": "Ethereum",
        "protocol": "Landshares",
        "token_symbol": "LANS",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 6.50,
        "risk_score": 4,
        "liquidity_score": 3,
        "regulatory_score": 7,
        "min_investment_usd": 100,
        "inception_date": "2022-06-01",
        "description": "Fractional US farmland ownership. Passive income from crop leases + land appreciation.",
        "tags": ["retail", "real-estate", "farmland", "agriculture"],
    },
    {
        "id": "BLOCKS_COM",
        "name": "Blocksquare Commercial Real Estate",
        "category": "Real Estate",
        "subcategory": "Commercial",
        "chain": "Ethereum",
        "protocol": "Blocksquare",
        "token_symbol": "BST",
        "coingecko_id": "blocksquare",
        "defillama_slug": None,
        "expected_yield_pct": 7.00,
        "risk_score": 5,
        "liquidity_score": 4,
        "regulatory_score": 7,
        "min_investment_usd": 100,
        "inception_date": "2020-01-01",
        "description": "European commercial property tokenization platform. Hotels, offices, retail spaces.",
        "tags": ["retail", "real-estate", "commercial", "europe"],
    },
    {
        "id": "DIGISHARES",
        "name": "DigiShares Real Estate Tokenization",
        "category": "Real Estate",
        "subcategory": "Commercial / Residential",
        "chain": "Ethereum / BSC",
        "protocol": "DigiShares",
        "token_symbol": "DGS",
        "coingecko_id": "digishares",
        "defillama_slug": None,
        "expected_yield_pct": 7.50,
        "risk_score": 5,
        "liquidity_score": 4,
        "regulatory_score": 7,
        "min_investment_usd": 500,
        "inception_date": "2019-01-01",
        "description": "White-label tokenization platform for real estate developers. Global coverage.",
        "tags": ["retail", "real-estate", "white-label", "global"],
    },

    # ── COMMODITIES ──────────────────────────────────────────────────────────
    {
        "id": "PAXG",
        "name": "Pax Gold",
        "category": "Commodities",
        "subcategory": "Gold",
        "chain": "Ethereum",
        "protocol": "Paxos",
        "token_symbol": "PAXG",
        "coingecko_id": "pax-gold",
        "defillama_slug": None,
        "expected_yield_pct": 0.0,
        "risk_score": 2,
        "liquidity_score": 9,
        "regulatory_score": 9,
        "min_investment_usd": 1,
        "inception_date": "2019-09-01",
        "description": "Each PAXG = 1 fine troy oz of gold in LBMA-accredited vaults. Redeemable for physical gold. NYDFS regulated.",
        "tags": ["retail", "gold", "commodity", "store-of-value", "nydfs"],
    },
    {
        "id": "XAUT",
        "name": "Tether Gold",
        "category": "Commodities",
        "subcategory": "Gold",
        "chain": "Ethereum / Tron",
        "protocol": "Tether",
        "token_symbol": "XAUt",
        "coingecko_id": "tether-gold",
        "defillama_slug": None,
        "expected_yield_pct": 0.0,
        "risk_score": 3,
        "liquidity_score": 9,
        "regulatory_score": 7,
        "min_investment_usd": 1,
        "inception_date": "2020-01-01",
        "description": "Gold-backed token by Tether. Each token = 1 troy fine ounce on specific gold bars in Switzerland.",
        "tags": ["retail", "gold", "commodity", "tether"],
    },
    {
        "id": "CACHE_GOLD",
        "name": "Cache Gold Token",
        "category": "Commodities",
        "subcategory": "Gold",
        "chain": "Ethereum",
        "protocol": "Cache Gold",
        "token_symbol": "CGT",
        "coingecko_id": "cache-gold",
        "defillama_slug": None,
        "expected_yield_pct": 0.0,
        "risk_score": 3,
        "liquidity_score": 6,
        "regulatory_score": 7,
        "min_investment_usd": 1,
        "inception_date": "2019-01-01",
        "description": "Physical gold stored in Singapore FreePort. Each CGT = 1 gram of gold. Storage fee applies.",
        "tags": ["retail", "gold", "commodity", "singapore"],
    },
    {
        "id": "BACKED_SILVER",
        "name": "Backed Silver",
        "category": "Commodities",
        "subcategory": "Silver",
        "chain": "Ethereum",
        "protocol": "Backed Finance",
        "token_symbol": "bXAG",
        "coingecko_id": None,
        "defillama_slug": "backed-finance",
        "expected_yield_pct": 0.0,
        "risk_score": 4,
        "liquidity_score": 6,
        "regulatory_score": 7,
        "min_investment_usd": 1,
        "inception_date": "2022-01-01",
        "description": "Tokenized silver-backed ETC. Physical silver stored in Swiss vaults. Backed by iShares Silver Trust.",
        "tags": ["retail", "silver", "commodity", "swiss"],
    },
    {
        "id": "BACKED_OIL",
        "name": "Backed Oil",
        "category": "Commodities",
        "subcategory": "Energy",
        "chain": "Ethereum",
        "protocol": "Backed Finance",
        "token_symbol": "bOIL",
        "coingecko_id": None,
        "defillama_slug": "backed-finance",
        "expected_yield_pct": 0.0,
        "risk_score": 7,
        "liquidity_score": 6,
        "regulatory_score": 6,
        "min_investment_usd": 1,
        "inception_date": "2022-06-01",
        "description": "Tokenized crude oil exposure backed by ProShares Ultra DJ-AIG Crude Oil ETF.",
        "tags": ["retail", "oil", "commodity", "energy"],
    },

    # ── CORPORATE BONDS / FIXED INCOME ──────────────────────────────────────
    {
        "id": "BACKED_LQD",
        "name": "Backed iShares USD Corporate Bond ETF",
        "category": "Government Bonds",
        "subcategory": "Bond ETF",
        "chain": "Ethereum",
        "protocol": "Backed Finance",
        "token_symbol": "bLQD",
        "coingecko_id": None,
        "defillama_slug": "backed-finance",
        "expected_yield_pct": 4.50,
        "risk_score": 3,
        "liquidity_score": 7,
        "regulatory_score": 8,
        "min_investment_usd": 1,
        "inception_date": "2021-12-01",
        "description": "Tokenized iShares iBoxx USD Investment Grade Corporate Bond ETF. Swiss FINMA-supervised, 1:1 backing.",
        "tags": ["retail", "corporate-bond", "etf", "ig", "swiss"],
    },
    {
        "id": "BACKED_CSPX",
        "name": "Backed S&P 500 Tracker",
        "category": "Tokenized Equities",
        "subcategory": "Index",
        "chain": "Ethereum / Gnosis",
        "protocol": "Backed Finance",
        "token_symbol": "bCSPX",
        "coingecko_id": "backed-cspx",
        "defillama_slug": "backed-finance",
        "expected_yield_pct": 10.0,
        "risk_score": 5,
        "liquidity_score": 7,
        "regulatory_score": 8,
        "min_investment_usd": 1,
        "inception_date": "2022-03-01",
        "description": "Tokenized S&P 500 ETF exposure on-chain. FINMA-supervised. Non-US investors only.",
        "tags": ["retail", "equities", "sp500", "index", "swiss"],
    },
    {
        "id": "SWARM_TSLA",
        "name": "Swarm Tesla Stock Token",
        "category": "Tokenized Equities",
        "subcategory": "Single Stock",
        "chain": "Polygon",
        "protocol": "Swarm Markets",
        "token_symbol": "sTSLA",
        "coingecko_id": None,
        "defillama_slug": "swarm",
        "expected_yield_pct": 0.0,
        "risk_score": 8,
        "liquidity_score": 7,
        "regulatory_score": 8,
        "min_investment_usd": 1,
        "inception_date": "2021-11-01",
        "description": "Fully-backed tokenized TSLA shares on Polygon. BaFin-licensed. 24/7 trading vs T+2 settlement.",
        "tags": ["retail", "equities", "single-stock", "bafin", "germany"],
    },
    {
        "id": "SWARM_AAPL",
        "name": "Swarm Apple Stock Token",
        "category": "Tokenized Equities",
        "subcategory": "Single Stock",
        "chain": "Polygon",
        "protocol": "Swarm Markets",
        "token_symbol": "sAAPL",
        "coingecko_id": None,
        "defillama_slug": "swarm",
        "expected_yield_pct": 0.0,
        "risk_score": 6,
        "liquidity_score": 7,
        "regulatory_score": 8,
        "min_investment_usd": 1,
        "inception_date": "2021-11-01",
        "description": "Fully-backed tokenized AAPL shares. BaFin-licensed, fully regulated German marketplace.",
        "tags": ["retail", "equities", "single-stock", "bafin", "germany"],
    },

    # ── INFRASTRUCTURE ───────────────────────────────────────────────────────
    {
        "id": "ENERGYFI",
        "name": "EnergyFi Solar Infrastructure",
        "category": "Infrastructure",
        "subcategory": "Renewable Energy",
        "chain": "Ethereum",
        "protocol": "EnergyFi",
        "token_symbol": "EFI",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 9.00,
        "risk_score": 5,
        "liquidity_score": 4,
        "regulatory_score": 6,
        "min_investment_usd": 500,
        "inception_date": "2022-05-01",
        "description": "Tokenized solar energy infrastructure. Revenue from energy sales creates on-chain yield.",
        "tags": ["retail", "infrastructure", "solar", "green-energy"],
    },
    {
        "id": "ONDO_INFRA",
        "name": "Infrastructure Debt Fund",
        "category": "Infrastructure",
        "subcategory": "Infrastructure Debt",
        "chain": "Ethereum",
        "protocol": "Ondo Finance",
        "token_symbol": "ONDO",
        "coingecko_id": "ondo-finance",
        "defillama_slug": "ondo-finance",
        "expected_yield_pct": 7.50,
        "risk_score": 4,
        "liquidity_score": 5,
        "regulatory_score": 8,
        "min_investment_usd": 100_000,
        "inception_date": "2023-12-01",
        "description": "Senior secured infrastructure debt in transportation, utilities, and social infrastructure.",
        "tags": ["institutional", "infrastructure", "senior-secured", "debt"],
    },

    # ── CARBON CREDITS ───────────────────────────────────────────────────────
    {
        "id": "MCO2",
        "name": "Moss.Earth Carbon Credit Token",
        "category": "Carbon Credits",
        "subcategory": "Voluntary Carbon Market",
        "chain": "Ethereum / Polygon",
        "protocol": "Moss.Earth",
        "token_symbol": "MCO2",
        "coingecko_id": "moss-carbon-credit",
        "defillama_slug": None,
        "expected_yield_pct": 0.0,
        "risk_score": 7,
        "liquidity_score": 7,
        "regulatory_score": 6,
        "min_investment_usd": 1,
        "inception_date": "2020-08-01",
        "description": "Each MCO2 = 1 tonne CO2 offset from Amazon rainforest preservation projects. VCS certified.",
        "tags": ["retail", "carbon-credit", "amazon", "vcs", "voluntary"],
    },
    {
        "id": "NBO",
        "name": "Toucan Protocol Nature Carbon Tonne",
        "category": "Carbon Credits",
        "subcategory": "Nature-Based",
        "chain": "Polygon",
        "protocol": "Toucan Protocol",
        "token_symbol": "NCT",
        "coingecko_id": "toucan-protocol-nature-carbon-tonne",
        "defillama_slug": "toucan",
        "expected_yield_pct": 0.0,
        "risk_score": 8,
        "liquidity_score": 8,
        "regulatory_score": 5,
        "min_investment_usd": 1,
        "inception_date": "2021-10-01",
        "description": "Pool of Verra-certified nature-based carbon credits on Polygon. Tradeable DeFi carbon pool.",
        "tags": ["retail", "carbon-credit", "nature-based", "toucan", "defi-native"],
    },
    {
        "id": "KLIMA",
        "name": "KlimaDAO Carbon Treasury",
        "category": "Carbon Credits",
        "subcategory": "Carbon Treasury",
        "chain": "Polygon",
        "protocol": "KlimaDAO",
        "token_symbol": "KLIMA",
        "coingecko_id": "klima-dao",
        "defillama_slug": "klimadao",
        "expected_yield_pct": 5.00,
        "risk_score": 8,
        "liquidity_score": 8,
        "regulatory_score": 5,
        "min_investment_usd": 1,
        "inception_date": "2021-10-18",
        "description": "DAO governing a treasury of tokenized carbon offsets. Staking yields paid in KLIMA.",
        "tags": ["retail", "carbon-credit", "dao", "staking", "treasury"],
    },

    # ── INTELLECTUAL PROPERTY / ROYALTIES ────────────────────────────────────
    {
        "id": "ROYAL_MUSIC",
        "name": "Royal Music Royalty Tokens",
        "category": "Intellectual Property",
        "subcategory": "Music Royalties",
        "chain": "Ethereum",
        "protocol": "Royal",
        "token_symbol": "LDA",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 6.50,
        "risk_score": 6,
        "liquidity_score": 4,
        "regulatory_score": 7,
        "min_investment_usd": 100,
        "inception_date": "2021-11-01",
        "description": "Fractional music streaming royalties from artists like Nas, The Chainsmokers, Kygo.",
        "tags": ["retail", "music-royalties", "ip", "streaming"],
    },
    {
        "id": "OPULOUS",
        "name": "Opulous Music IP Tokens",
        "category": "Intellectual Property",
        "subcategory": "Music Royalties",
        "chain": "Algorand",
        "protocol": "Opulous",
        "token_symbol": "OPUL",
        "coingecko_id": "opulous",
        "defillama_slug": None,
        "expected_yield_pct": 8.00,
        "risk_score": 7,
        "liquidity_score": 5,
        "regulatory_score": 7,
        "min_investment_usd": 100,
        "inception_date": "2021-07-01",
        "description": "Music copyright-backed DeFi loans and fractional royalty tokens on Algorand.",
        "tags": ["retail", "music-royalties", "ip", "algorand", "defi"],
    },

    # ── ART & COLLECTIBLES ───────────────────────────────────────────────────
    {
        "id": "MASTERWORKS",
        "name": "Masterworks Fine Art Shares",
        "category": "Art & Collectibles",
        "subcategory": "Fine Art",
        "chain": "Off-chain / Reg A+",
        "protocol": "Masterworks",
        "token_symbol": "ART",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 14.0,
        "risk_score": 7,
        "liquidity_score": 3,
        "regulatory_score": 9,
        "min_investment_usd": 500,
        "inception_date": "2017-01-01",
        "description": "SEC-qualified shares in authenticated blue-chip art (Banksy, Basquiat, Picasso). Average 14.1% annualized.",
        "tags": ["retail", "fine-art", "collectibles", "sec-reg-a", "illiquid"],
    },
    {
        "id": "FREEPORT_ART",
        "name": "Freeport Fractional Art",
        "category": "Art & Collectibles",
        "subcategory": "Fine Art",
        "chain": "Ethereum",
        "protocol": "Freeport",
        "token_symbol": "FREEPORT",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 10.0,
        "risk_score": 8,
        "liquidity_score": 3,
        "regulatory_score": 7,
        "min_investment_usd": 100,
        "inception_date": "2022-01-01",
        "description": "Tokenized fractional ownership of physical art stored in climate-controlled vaults.",
        "tags": ["retail", "fine-art", "fractional", "nft"],
    },

    # ── PRIVATE EQUITY ───────────────────────────────────────────────────────
    {
        "id": "FORGE_EQUITY",
        "name": "Forge Private Market Equity",
        "category": "Private Equity",
        "subcategory": "Pre-IPO / Secondary",
        "chain": "Ethereum",
        "protocol": "Forge Global / INX",
        "token_symbol": "INX",
        "coingecko_id": "inx-token",
        "defillama_slug": None,
        "expected_yield_pct": 20.0,
        "risk_score": 8,
        "liquidity_score": 4,
        "regulatory_score": 8,
        "min_investment_usd": 1_000,
        "inception_date": "2021-09-01",
        "description": "Tokenized pre-IPO and secondary market private equity. Access to Stripe, SpaceX, Databricks-type deals.",
        "tags": ["institutional", "private-equity", "pre-ipo", "secondary"],
    },
    {
        "id": "ADDX_PE",
        "name": "ADDX Private Equity Funds",
        "category": "Private Equity",
        "subcategory": "Fund of Funds",
        "chain": "Ethereum",
        "protocol": "ADDX",
        "token_symbol": "ADDX",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 15.0,
        "risk_score": 7,
        "liquidity_score": 4,
        "regulatory_score": 9,
        "min_investment_usd": 10_000,
        "inception_date": "2020-01-01",
        "description": "MAS-licensed Singapore exchange for tokenized PE funds, hedge funds, and private credit.",
        "tags": ["institutional", "private-equity", "singapore", "mas-licensed"],
    },

    # ── INSURANCE & ALTERNATIVE RISK ─────────────────────────────────────────
    {
        "id": "NEXUS_MUTUAL",
        "name": "Nexus Mutual Risk Pools",
        "category": "Insurance",
        "subcategory": "DeFi Risk Cover",
        "chain": "Ethereum",
        "protocol": "Nexus Mutual",
        "token_symbol": "NXM",
        "coingecko_id": "nexus-mutual",
        "defillama_slug": "nexus-mutual",
        "expected_yield_pct": 15.0,
        "risk_score": 8,
        "liquidity_score": 7,
        "regulatory_score": 6,
        "min_investment_usd": 100,
        "inception_date": "2019-05-23",
        "description": "Decentralized mutual insurance protocol. Stake NXM to underwrite covers, earn assessment rewards.",
        "tags": ["retail", "insurance", "defi-cover", "mutual"],
    },
    {
        "id": "RISK_HARBOR",
        "name": "Risk Harbor Structured Insurance",
        "category": "Insurance",
        "subcategory": "Protocol Insurance",
        "chain": "Ethereum",
        "protocol": "Risk Harbor",
        "token_symbol": "HARBOR",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 12.0,
        "risk_score": 7,
        "liquidity_score": 5,
        "regulatory_score": 5,
        "min_investment_usd": 1_000,
        "inception_date": "2021-07-01",
        "description": "Automated smart contract insurance using actuarial models instead of human voting.",
        "tags": ["institutional", "insurance", "automated", "protocol-cover"],
    },

    # ── SUPPLY CHAIN / TRADE FINANCE ─────────────────────────────────────────
    {
        "id": "CREDIX_TRADE",
        "name": "Credix Trade Finance Pools",
        "category": "Trade Finance",
        "subcategory": "LatAm Trade Finance",
        "chain": "Solana",
        "protocol": "Credix",
        "token_symbol": "CREDIX",
        "coingecko_id": "credix-finance",
        "defillama_slug": "credix",
        "expected_yield_pct": 14.0,
        "risk_score": 6,
        "liquidity_score": 5,
        "regulatory_score": 7,
        "min_investment_usd": 100_000,
        "inception_date": "2022-01-01",
        "description": "Institutional credit marketplace on Solana. LatAm B2B trade finance, working capital loans.",
        "tags": ["institutional", "trade-finance", "latam", "solana", "private-credit"],
    },
    {
        "id": "POLYTRADE",
        "name": "Polytrade Invoice Financing",
        "category": "Trade Finance",
        "subcategory": "Invoice Financing",
        "chain": "Polygon",
        "protocol": "Polytrade",
        "token_symbol": "TRADE",
        "coingecko_id": "polytrade",
        "defillama_slug": None,
        "expected_yield_pct": 10.0,
        "risk_score": 6,
        "liquidity_score": 5,
        "regulatory_score": 7,
        "min_investment_usd": 1_000,
        "inception_date": "2021-10-01",
        "description": "Invoice financing using USDC. Invoices from Fortune 500 companies as collateral.",
        "tags": ["retail", "trade-finance", "invoice", "polygon"],
    },

    # ── MAKER DAO RWA VAULTS ──────────────────────────────────────────────────
    {
        "id": "MKR_RWA",
        "name": "MakerDAO RWA Vaults",
        "category": "Private Credit",
        "subcategory": "Institutional RWA Vaults",
        "chain": "Ethereum",
        "protocol": "MakerDAO / Sky",
        "token_symbol": "MKR",
        "coingecko_id": "maker",
        "defillama_slug": "makerdao",
        "expected_yield_pct": 5.80,
        "risk_score": 3,
        "liquidity_score": 8,
        "regulatory_score": 7,
        "min_investment_usd": 1,
        "inception_date": "2022-04-01",
        "description": "MakerDAO's off-chain collateral vaults holding T-bills, corporate bonds, and real estate. Backing DAI stablecoin.",
        "tags": ["institutional", "private-credit", "makerdao", "dai-backing"],
    },

    # ── HASHNOTE — Largest institutional T-bill token ────────────────────────
    {
        "id": "USYC",
        "name": "Hashnote US Yield Coin",
        "category": "Government Bonds",
        "subcategory": "US Treasury",
        "chain": "Ethereum",
        "protocol": "Hashnote",
        "token_symbol": "USYC",
        "coingecko_id": None,
        "defillama_slug": "hashnote",
        "expected_yield_pct": 4.450,
        "risk_score": 1,
        "liquidity_score": 8,
        "regulatory_score": 9,
        "min_investment_usd": 100_000,
        "inception_date": "2023-10-01",
        "description": "DRW/Cumberland-backed institutional T-bill fund. One of the top 3 tokenized treasury vehicles by TVL ($500M–$1B).",
        "tags": ["institutional", "treasury", "drw", "cumberland", "accredited"],
    },
    {
        "id": "USCC",
        "name": "Superstate Crypto Carry Fund",
        "category": "Private Credit",
        "subcategory": "Crypto Carry",
        "chain": "Ethereum",
        "protocol": "Superstate",
        "token_symbol": "USCC",
        "coingecko_id": None,
        "defillama_slug": "superstate",
        "expected_yield_pct": 9.00,
        "risk_score": 4,
        "liquidity_score": 7,
        "regulatory_score": 8,
        "min_investment_usd": 100_000,
        "inception_date": "2024-06-01",
        "description": "Tokenized fund capturing crypto carry premium (perpetual funding rates, basis). Higher yield vs pure T-bill.",
        "tags": ["institutional", "carry-trade", "crypto-basis", "superstate"],
    },
    {
        "id": "CLEARPOOL_USDC",
        "name": "Clearpool Institutional Credit Pools",
        "category": "Private Credit",
        "subcategory": "Unsecured Institutional",
        "chain": "Ethereum / Polygon / Arbitrum / Optimism",
        "protocol": "Clearpool",
        "token_symbol": "CPOOL",
        "coingecko_id": "clearpool",
        "defillama_slug": "clearpool",
        "expected_yield_pct": 9.50,
        "risk_score": 6,
        "liquidity_score": 7,
        "regulatory_score": 7,
        "min_investment_usd": 0,
        "inception_date": "2022-03-01",
        "description": "Permissionless single-borrower pools for institutional unsecured credit. Dynamic interest via utilization curve.",
        "tags": ["retail", "private-credit", "unsecured", "multi-chain"],
    },
    {
        "id": "FLOWCARBON_GNT",
        "name": "Flowcarbon Goodness Nature Token",
        "category": "Carbon Credits",
        "subcategory": "Nature-Based",
        "chain": "Polygon",
        "protocol": "Flowcarbon",
        "token_symbol": "GNT",
        "coingecko_id": "flowcarbon",
        "defillama_slug": None,
        "expected_yield_pct": 0.0,
        "risk_score": 8,
        "liquidity_score": 5,
        "regulatory_score": 6,
        "min_investment_usd": 1,
        "inception_date": "2022-05-01",
        "description": "a16z + Samsung-backed nature-based carbon credits on Polygon. VCS and Gold Standard certified offsets.",
        "tags": ["retail", "carbon-credit", "nature-based", "a16z", "vcs"],
    },
    {
        "id": "BACKED_IBTA",
        "name": "Backed US Treasury Bond ETF Token",
        "category": "Government Bonds",
        "subcategory": "US Treasury",
        "chain": "Ethereum / Gnosis",
        "protocol": "Backed Finance",
        "token_symbol": "bIBTA",
        "coingecko_id": None,
        "defillama_slug": "backed-finance",
        "expected_yield_pct": 4.150,
        "risk_score": 1,
        "liquidity_score": 7,
        "regulatory_score": 8,
        "min_investment_usd": 1,
        "inception_date": "2022-09-01",
        "description": "Tokenized iShares USD Treasury Bond 1-3yr ETF (bIBTA). Swiss FINMA-supervised. Non-US investors.",
        "tags": ["retail", "treasury", "etf", "swiss", "non-us"],
    },
    {
        "id": "AGROTOKEN_SOY",
        "name": "Agrotoken Soy Grain Token",
        "category": "Commodities",
        "subcategory": "Agricultural",
        "chain": "Ethereum / Algorand",
        "protocol": "Agrotoken",
        "token_symbol": "SOYA",
        "coingecko_id": "agrotoken",
        "defillama_slug": None,
        "expected_yield_pct": 0.0,
        "risk_score": 6,
        "liquidity_score": 4,
        "regulatory_score": 6,
        "min_investment_usd": 100,
        "inception_date": "2021-08-01",
        "description": "Argentine soy, corn, and wheat grain tokens used as DeFi collateral by farmers. Pioneer in agri-RWA.",
        "tags": ["retail", "agriculture", "commodity", "argentina", "latam"],
    },
    {
        "id": "ANOTE_MUSIC",
        "name": "ANote Music Publishing Royalties",
        "category": "Intellectual Property",
        "subcategory": "Music Publishing",
        "chain": "Ethereum",
        "protocol": "ANote Music",
        "token_symbol": "ANOTE",
        "coingecko_id": "anote-music",
        "defillama_slug": None,
        "expected_yield_pct": 7.50,
        "risk_score": 6,
        "liquidity_score": 4,
        "regulatory_score": 7,
        "min_investment_usd": 100,
        "inception_date": "2020-06-01",
        "description": "Fractional music publishing rights. Revenue from radio, TV, sync licensing, streaming.",
        "tags": ["retail", "music-royalties", "publishing", "ip", "marketplace"],
    },
    {
        "id": "ENZYME_RWA",
        "name": "Enzyme Finance RWA Vaults",
        "category": "Private Credit",
        "subcategory": "Automated Vault",
        "chain": "Ethereum / Polygon",
        "protocol": "Enzyme Finance",
        "token_symbol": "MLN",
        "coingecko_id": "melon",
        "defillama_slug": "enzyme",
        "expected_yield_pct": 8.00,
        "risk_score": 5,
        "liquidity_score": 7,
        "regulatory_score": 7,
        "min_investment_usd": 0,
        "inception_date": "2019-01-01",
        "description": "On-chain fund management with automated rebalancing. Supports RWA tokens as vault assets.",
        "tags": ["retail", "automated-vault", "fund-management", "defi-native"],
    },

    # ── AVALANCHE — KKR, Apollo, Hamilton Lane (via Securitize) ──────────────
    {
        "id": "HAMILTON_SCOPE",
        "name": "Hamilton Lane SCOPE Token",
        "category": "Private Equity",
        "subcategory": "Private Equity Fund",
        "chain": "Avalanche / Polygon / Ethereum",
        "protocol": "Hamilton Lane / Securitize",
        "token_symbol": "SCOPE",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 12.5,
        "risk_score": 6,
        "liquidity_score": 5,
        "regulatory_score": 9,
        "min_investment_usd": 10_000,
        "inception_date": "2023-01-01",
        "description": "Tokenized access to Hamilton Lane's $823B AUM private market fund via Securitize. First major PE firm fully tokenized on Avalanche.",
        "tags": ["institutional", "private-equity", "hamilton-lane", "avalanche", "securitize", "accredited"],
    },
    {
        "id": "KKR_HEALTH_TOKEN",
        "name": "KKR Health Care Strategic Growth Fund Token",
        "category": "Private Equity",
        "subcategory": "Healthcare PE",
        "chain": "Avalanche",
        "protocol": "KKR / Securitize",
        "token_symbol": "KKR-HLTH",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 15.0,
        "risk_score": 7,
        "liquidity_score": 4,
        "regulatory_score": 9,
        "min_investment_usd": 10_000,
        "inception_date": "2022-09-01",
        "description": "KKR's healthcare-focused PE fund tokenized on Avalanche via Securitize. Pioneering tokenized private equity for qualified purchasers.",
        "tags": ["institutional", "private-equity", "kkr", "healthcare", "avalanche", "securitize", "accredited"],
    },
    {
        "id": "APOLLO_CREDIT_TOKEN",
        "name": "Apollo Diversified Credit Fund Token",
        "category": "Private Credit",
        "subcategory": "Diversified Credit",
        "chain": "Avalanche",
        "protocol": "Apollo Global / Securitize",
        "token_symbol": "ACRED",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 11.0,
        "risk_score": 5,
        "liquidity_score": 5,
        "regulatory_score": 9,
        "min_investment_usd": 10_000,
        "inception_date": "2024-01-01",
        "description": "Apollo's $500B AUM diversified credit strategy tokenized on Avalanche. Accredited investor access to institutional private credit.",
        "tags": ["institutional", "private-credit", "apollo", "avalanche", "securitize", "accredited"],
    },
    {
        "id": "SPIKO_TBILL_AVAX",
        "name": "Spiko US T-Bills on Avalanche",
        "category": "Government Bonds",
        "subcategory": "US Treasury",
        "chain": "Avalanche",
        "protocol": "Spiko",
        "token_symbol": "USKT",
        "coingecko_id": None,
        "defillama_slug": "spiko",
        "expected_yield_pct": 4.4,
        "risk_score": 1,
        "liquidity_score": 8,
        "regulatory_score": 9,
        "min_investment_usd": 100,
        "inception_date": "2023-11-01",
        "description": "Spiko tokenized US and EU T-bills on Avalanche. AMF-regulated (France). Retail accessible from €100 with daily accrual.",
        "tags": ["retail", "treasury", "avalanche", "amf-regulated", "france", "daily-yield"],
    },

    # ── BASE CHAIN (Coinbase L2) — Dinari dShares, RWA ecosystem ─────────────
    {
        "id": "DINARI_DSHARES",
        "name": "Dinari dShares Tokenized Stocks",
        "category": "Tokenized Equities",
        "subcategory": "Tokenized Stocks",
        "chain": "Base / Arbitrum / Ethereum",
        "protocol": "Dinari",
        "token_symbol": "DSHR",
        "coingecko_id": None,
        "defillama_slug": "dinari",
        "expected_yield_pct": 9.0,
        "risk_score": 5,
        "liquidity_score": 8,
        "regulatory_score": 9,
        "min_investment_usd": 1,
        "inception_date": "2023-07-01",
        "description": "Fully-regulated 1:1 stock-backed tokens on Base and Arbitrum. 200+ US equities (AAPL, MSFT, NVDA, SPY, QQQ). 24/7 trading, T+0 settlement.",
        "tags": ["retail", "equities", "tokenized-stocks", "base", "arbitrum", "regulated", "24-7-trading", "dinari"],
    },
    {
        "id": "OPENTRADE_BASE",
        "name": "OpenTrade On-Chain Treasury Vaults",
        "category": "Government Bonds",
        "subcategory": "US Treasury",
        "chain": "Base / Ethereum",
        "protocol": "OpenTrade",
        "token_symbol": "OTK",
        "coingecko_id": None,
        "defillama_slug": "opentrade",
        "expected_yield_pct": 4.35,
        "risk_score": 2,
        "liquidity_score": 7,
        "regulatory_score": 8,
        "min_investment_usd": 50_000,
        "inception_date": "2023-10-01",
        "description": "Circle-backed institutional treasury vaults on Base. Protocols earn T-bill yields on idle USDC. FCA-regulated, daily liquidity.",
        "tags": ["institutional", "treasury", "base", "usdc-yield", "circle-backed", "fca-regulated"],
    },

    # ── HEDERA (HBAR) — Institutional tokenization ────────────────────────────
    {
        "id": "ARCHAX_HEDERA",
        "name": "Archax Tokenized Money Market Fund on Hedera",
        "category": "Government Bonds",
        "subcategory": "Money Market",
        "chain": "Hedera",
        "protocol": "Archax / Hedera",
        "token_symbol": "aMMF",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 4.42,
        "risk_score": 1,
        "liquidity_score": 7,
        "regulatory_score": 9,
        "min_investment_usd": 100_000,
        "inception_date": "2023-06-01",
        "description": "FCA-regulated UK exchange Archax tokenizing T-bills and money market funds on Hedera. Standard Chartered and Cboe partnership.",
        "tags": ["institutional", "money-market", "hedera", "archax", "fca-regulated", "standard-chartered"],
    },
    {
        "id": "HEDERA_STABLECOIN",
        "name": "Hedera Tokenized Asset Platform (HSCS)",
        "category": "Private Credit",
        "subcategory": "Institutional RWA",
        "chain": "Hedera",
        "protocol": "Hedera / DLA Piper",
        "token_symbol": "HBAR-RWA",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 7.5,
        "risk_score": 4,
        "liquidity_score": 6,
        "regulatory_score": 9,
        "min_investment_usd": 100_000,
        "inception_date": "2022-06-01",
        "description": "Enterprise RWA tokenization on Hedera via Hedera Token Service. DLA Piper legal framework. aBey, Standard Chartered, Cboe Digital integrations.",
        "tags": ["institutional", "private-credit", "hedera", "enterprise", "dla-piper", "cboe"],
    },

    # ── XRP LEDGER — Ripple RWA ecosystem ─────────────────────────────────────
    {
        "id": "RLUSD",
        "name": "Ripple USD (RLUSD)",
        "category": "Government Bonds",
        "subcategory": "Yield Stablecoin",
        "chain": "XRP Ledger / Ethereum",
        "protocol": "Ripple",
        "token_symbol": "RLUSD",
        "coingecko_id": "ripple-usd",
        "defillama_slug": None,
        "expected_yield_pct": 4.7,
        "risk_score": 2,
        "liquidity_score": 8,
        "regulatory_score": 8,
        "min_investment_usd": 1,
        "inception_date": "2024-12-01",
        "description": "Ripple's enterprise-grade stablecoin backed by US Treasuries and cash equivalents. NYDFS approved. Bridges XRP Ledger to DeFi.",
        "tags": ["retail", "stablecoin", "xrpl", "ripple", "treasury-backed", "nydfs"],
    },
    {
        "id": "ARCHAX_XRPL",
        "name": "Archax Tokenized T-Bills on XRP Ledger",
        "category": "Government Bonds",
        "subcategory": "US Treasury",
        "chain": "XRP Ledger",
        "protocol": "Archax / Ripple",
        "token_symbol": "aTBILL",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 4.35,
        "risk_score": 1,
        "liquidity_score": 7,
        "regulatory_score": 9,
        "min_investment_usd": 100_000,
        "inception_date": "2024-03-01",
        "description": "FCA-regulated tokenized T-bills on XRP Ledger. Part of Ripple's $1B+ institutional RWA strategy and XRPL AMM integration.",
        "tags": ["institutional", "treasury", "xrpl", "archax", "ripple", "fca-regulated"],
    },

    # ── TEZOS — SocGen FORGE and EU-regulated security tokens ─────────────────
    {
        "id": "SOCGEN_FORGE",
        "name": "Societe Generale FORGE Security Tokens",
        "category": "Government Bonds",
        "subcategory": "Covered Bonds",
        "chain": "Tezos / Ethereum",
        "protocol": "SG FORGE",
        "token_symbol": "OFH",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 4.2,
        "risk_score": 1,
        "liquidity_score": 5,
        "regulatory_score": 10,
        "min_investment_usd": 100_000,
        "inception_date": "2019-04-01",
        "description": "France's largest bank SocGen issued €100M+ covered bonds and structured products as MiCA-compliant security tokens on Tezos and Ethereum.",
        "tags": ["institutional", "covered-bonds", "tezos", "societe-generale", "mica-compliant", "eu-regulated"],
    },
    {
        "id": "AXA_BOND_TEZ",
        "name": "AXA Investment Managers Tokenized Bond",
        "category": "Government Bonds",
        "subcategory": "Corporate Bonds",
        "chain": "Tezos",
        "protocol": "AXA Investment Managers",
        "token_symbol": "AXA-BOND",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 4.5,
        "risk_score": 2,
        "liquidity_score": 4,
        "regulatory_score": 10,
        "min_investment_usd": 100_000,
        "inception_date": "2021-06-01",
        "description": "AXA IM tokenized green bond on Tezos. Part of the EU Blockchain Securities Pilot Regime. €200B AUM manager using on-chain settlement.",
        "tags": ["institutional", "corporate-bonds", "tezos", "axa", "green-bond", "eu-pilot", "mica"],
    },

    # ── PROVENANCE BLOCKCHAIN — Figure Technologies, USDF ─────────────────────
    {
        "id": "FIGURE_HELOC",
        "name": "Figure Technologies HELOC Token",
        "category": "Private Credit",
        "subcategory": "Mortgage / HELOC",
        "chain": "Provenance",
        "protocol": "Figure Technologies",
        "token_symbol": "FIG",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 8.5,
        "risk_score": 5,
        "liquidity_score": 5,
        "regulatory_score": 8,
        "min_investment_usd": 50_000,
        "inception_date": "2018-06-01",
        "description": "World's largest blockchain-native HELOC originator — $9B+ in loans originated on Provenance Blockchain. US home equity-backed credit.",
        "tags": ["institutional", "mortgage", "heloc", "provenance", "real-estate-credit", "accredited"],
    },
    {
        "id": "USDF_PROVENANCE",
        "name": "USDF Bank-Minted Stablecoin",
        "category": "Government Bonds",
        "subcategory": "Bank-Backed Stablecoin",
        "chain": "Provenance",
        "protocol": "USDF Consortium",
        "token_symbol": "USDF",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 4.15,
        "risk_score": 1,
        "liquidity_score": 6,
        "regulatory_score": 9,
        "min_investment_usd": 1,
        "inception_date": "2022-01-01",
        "description": "Bank-minted stablecoin on Provenance Blockchain backed by FDIC-insured deposits. NY Community Bank, Bell Bank, NBH Bank consortium.",
        "tags": ["institutional", "stablecoin", "provenance", "bank-backed", "fdic-insured", "consortium"],
    },

    # ── APTOS — Emerging institutional RWA ────────────────────────────────────
    {
        "id": "THALA_MOD",
        "name": "Thala Labs Move Dollar (MOD) on Aptos",
        "category": "Government Bonds",
        "subcategory": "Yield Stablecoin",
        "chain": "Aptos",
        "protocol": "Thala Labs",
        "token_symbol": "MOD",
        "coingecko_id": "move-dollar",
        "defillama_slug": "thala",
        "expected_yield_pct": 6.5,
        "risk_score": 4,
        "liquidity_score": 6,
        "regulatory_score": 6,
        "min_investment_usd": 1,
        "inception_date": "2023-01-01",
        "description": "Aptos-native CDP stablecoin partially backed by RWA collateral. Thala's DeFi suite leads Aptos ecosystem RWA adoption.",
        "tags": ["retail", "stablecoin", "aptos", "cdp", "rwa-collateral", "move-language"],
    },
    {
        "id": "ONDO_APTOS",
        "name": "Ondo Finance USDY on Aptos",
        "category": "Government Bonds",
        "subcategory": "Yield Stablecoin",
        "chain": "Aptos",
        "protocol": "Ondo Finance",
        "token_symbol": "USDY-APT",
        "coingecko_id": None,
        "defillama_slug": "ondo-finance",
        "expected_yield_pct": 4.35,
        "risk_score": 2,
        "liquidity_score": 7,
        "regulatory_score": 8,
        "min_investment_usd": 500,
        "inception_date": "2024-06-01",
        "description": "Ondo's USDY yield token deployed on Aptos, bringing T-bill-backed yield to the Aptos Move ecosystem.",
        "tags": ["retail", "stablecoin", "aptos", "treasury", "yield-bearing", "ondo"],
    },

    # ── CARDANO — RealFi and emerging tokenization ─────────────────────────────
    {
        "id": "REALFI_CARDANO",
        "name": "IOHK RealFi Tokenized Loans on Cardano",
        "category": "Private Credit",
        "subcategory": "Emerging Market Loans",
        "chain": "Cardano",
        "protocol": "IOHK / RealFi",
        "token_symbol": "REALFI",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 10.0,
        "risk_score": 6,
        "liquidity_score": 4,
        "regulatory_score": 7,
        "min_investment_usd": 500,
        "inception_date": "2021-11-01",
        "description": "Cardano's real-world finance initiative bridging DeFi to real economies in Africa and emerging markets. DID-based identity lending.",
        "tags": ["retail", "private-credit", "cardano", "emerging-markets", "africa", "identity", "realfi"],
    },
    {
        "id": "NMKR_CARDANO",
        "name": "NMKR Real Asset Tokenization on Cardano",
        "category": "Real Estate",
        "subcategory": "Multi-Asset Tokenization",
        "chain": "Cardano",
        "protocol": "NMKR",
        "token_symbol": "NMKR",
        "coingecko_id": "nmkr",
        "defillama_slug": None,
        "expected_yield_pct": 7.0,
        "risk_score": 6,
        "liquidity_score": 5,
        "regulatory_score": 7,
        "min_investment_usd": 100,
        "inception_date": "2022-03-01",
        "description": "Cardano's leading tokenization platform supporting real estate, art, and commodities. 10M+ NFTs minted. EU regulatory framework.",
        "tags": ["retail", "real-estate", "cardano", "tokenization", "multi-asset", "eu"],
    },

    # ── SUI — Emerging RWA ecosystem ──────────────────────────────────────────
    {
        "id": "BUCKET_SUI",
        "name": "Bucket Protocol RWA Stablecoin on Sui",
        "category": "Government Bonds",
        "subcategory": "Yield Stablecoin",
        "chain": "Sui",
        "protocol": "Bucket Protocol",
        "token_symbol": "BUCK",
        "coingecko_id": "bucket-protocol",
        "defillama_slug": "bucket-protocol",
        "expected_yield_pct": 6.0,
        "risk_score": 5,
        "liquidity_score": 6,
        "regulatory_score": 5,
        "min_investment_usd": 1,
        "inception_date": "2023-04-01",
        "description": "Sui-native CDP stablecoin with RWA collateral integration. Leading DeFi protocol on Sui exploring tokenized T-bill backing.",
        "tags": ["retail", "stablecoin", "sui", "cdp", "rwa-collateral"],
    },

    # ── TOKENIZED STOCKS — NASDAQ, Robinhood, DEX Platforms ───────────────────
    {
        "id": "ROBINHOOD_TOKENIZED",
        "name": "Robinhood Tokenized US Equities",
        "category": "Tokenized Equities",
        "subcategory": "Tokenized Stocks",
        "chain": "Arbitrum",
        "protocol": "Robinhood / Arbitrum",
        "token_symbol": "RHD-EQ",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 9.0,
        "risk_score": 4,
        "liquidity_score": 9,
        "regulatory_score": 9,
        "min_investment_usd": 1,
        "inception_date": "2024-06-01",
        "description": "Robinhood's 24/7 tokenized US stocks on Arbitrum for EU customers. 200+ equities, fractional shares, MiFID II compliant. Global expansion imminent.",
        "tags": ["retail", "equities", "tokenized-stocks", "arbitrum", "robinhood", "24-7-trading", "mifid2", "fractional"],
    },
    {
        "id": "NASDAQ_TOKENIZED",
        "name": "NASDAQ SEC-Approved Tokenized Equities Pilot",
        "category": "Tokenized Equities",
        "subcategory": "Tokenized Stocks",
        "chain": "Multiple",
        "protocol": "NASDAQ / DTC",
        "token_symbol": "NDAQ-T",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 10.0,
        "risk_score": 2,
        "liquidity_score": 10,
        "regulatory_score": 10,
        "min_investment_usd": 1,
        "inception_date": "2026-03-18",
        "description": "SEC approved March 18, 2026 — Russell 1000 stocks + S&P 500/Nasdaq-100 ETFs tokenized via DTC clearing. First token-settled trades targeted Q3 2026. Full T+0 instant settlement, 24/7 markets.",
        "tags": ["institutional", "equities", "nasdaq", "t0-settlement", "dtc", "tokenized-stocks", "sec-approved", "russell-1000", "sp500", "breaking-2026"],
    },
    {
        "id": "NYSE_TOKENIZED",
        "name": "NYSE / ICE Tokenized Securities Platform",
        "category": "Tokenized Equities",
        "subcategory": "Tokenized Stocks",
        "chain": "Multiple",
        "protocol": "NYSE / ICE / Bakkt",
        "token_symbol": "NYSE-T",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 9.5,
        "risk_score": 2,
        "liquidity_score": 9,
        "regulatory_score": 10,
        "min_investment_usd": 1,
        "inception_date": "2026-01-01",
        "description": "NYSE / Intercontinental Exchange developing tokenized securities platform: 24/7 trading, instant settlement, stablecoin funding. Leverages ICE's existing DTC membership and Bakkt digital asset infrastructure.",
        "tags": ["institutional", "equities", "nyse", "ice", "bakkt", "t0-settlement", "tokenized-stocks", "stablecoin-settlement", "24-7-trading"],
    },
    {
        "id": "ONDO_GLOBAL_MARKETS",
        "name": "Ondo Global Markets Tokenized Stocks & ETFs",
        "category": "Tokenized Equities",
        "subcategory": "Tokenized Stocks",
        "chain": "Ethereum / BNB Chain / Solana",
        "protocol": "Ondo Finance",
        "token_symbol": "ONDO-GM",
        "coingecko_id": "ondo-finance",
        "defillama_slug": "ondo-finance",
        "expected_yield_pct": 12.0,
        "risk_score": 3,
        "liquidity_score": 9,
        "regulatory_score": 9,
        "min_investment_usd": 1,
        "inception_date": "2025-09-01",
        "description": "#1 tokenized stocks platform. $600M+ TVL, 200+ U.S. stocks & ETFs (TSLA, NVDA, AAPL, MSFT, AMZN, QQQ, SPY), 60% market share. ADGM/Binance approved March 2026. Non-US investors via equity-linked notes. Ethereum/BNB/Solana.",
        "tags": ["retail", "equities", "ondo", "tokenized-stocks", "multinchain", "adgm", "binance", "metamask", "sp500", "nasdaq100", "ando-finance"],
    },
    {
        "id": "GAINS_TOKENIZED",
        "name": "Gains Network gTrade Tokenized Stocks (DEX)",
        "category": "Equities",
        "subcategory": "Synthetic Stocks / DEX",
        "chain": "Arbitrum / Polygon",
        "protocol": "Gains Network",
        "token_symbol": "GNS",
        "coingecko_id": "gains-network",
        "defillama_slug": "gains-network",
        "expected_yield_pct": 15.0,
        "risk_score": 7,
        "liquidity_score": 8,
        "regulatory_score": 6,
        "min_investment_usd": 10,
        "inception_date": "2021-06-01",
        "description": "Decentralized perpetual trading of 150+ tokenized stocks, forex, and crypto on Arbitrum/Polygon. 24/7 markets, up to 150x leverage.",
        "tags": ["retail", "equities", "synthetic-stocks", "dex", "leverage", "gains-network", "24-7-trading", "perpetuals"],
    },
    {
        "id": "TZERO_PLATFORM",
        "name": "tZERO Tokenized Securities Exchange",
        "category": "Tokenized Equities",
        "subcategory": "Security Token Exchange",
        "chain": "Ethereum",
        "protocol": "tZERO Group",
        "token_symbol": "TZROP",
        "coingecko_id": "tzero",
        "defillama_slug": None,
        "expected_yield_pct": 8.0,
        "risk_score": 6,
        "liquidity_score": 6,
        "regulatory_score": 10,
        "min_investment_usd": 100,
        "inception_date": "2018-08-01",
        "description": "First SEC-registered Alternative Trading System (ATS) for security tokens. Overstock-backed tokenized securities exchange with broker-dealer license.",
        "tags": ["institutional", "equities", "security-tokens", "ats", "sec-registered", "tzero", "broker-dealer"],
    },
    {
        "id": "BACKED_NASDAQ100",
        "name": "Backed Nasdaq-100 Tracker Token",
        "category": "Tokenized Equities",
        "subcategory": "Index",
        "chain": "Ethereum / Base",
        "protocol": "Backed Finance",
        "token_symbol": "bNDX",
        "coingecko_id": None,
        "defillama_slug": "backed-finance",
        "expected_yield_pct": 12.0,
        "risk_score": 6,
        "liquidity_score": 7,
        "regulatory_score": 8,
        "min_investment_usd": 1,
        "inception_date": "2023-06-01",
        "description": "Tokenized Invesco QQQ (Nasdaq-100) ETF on Ethereum and Base. FINMA-supervised. Non-US investors only. Tech sector exposure on-chain.",
        "tags": ["retail", "equities", "nasdaq100", "index", "qqq", "backed-finance", "swiss"],
    },
    {
        "id": "SYNTHETIX_STOCKS",
        "name": "Synthetix Synthetic Stocks (Kwenta)",
        "category": "Equities",
        "subcategory": "Synthetic Stocks / DEX",
        "chain": "Optimism / Base",
        "protocol": "Synthetix / Kwenta",
        "token_symbol": "SNX",
        "coingecko_id": "havven",
        "defillama_slug": "synthetix",
        "expected_yield_pct": 12.0,
        "risk_score": 7,
        "liquidity_score": 8,
        "regulatory_score": 5,
        "min_investment_usd": 1,
        "inception_date": "2018-06-01",
        "description": "Synthetix protocol enables on-chain synthetic exposure to stocks, indices, and forex via Kwenta DEX on Optimism and Base.",
        "tags": ["retail", "equities", "synthetic-stocks", "dex", "optimism", "kwenta", "snx", "perps"],
    },

    # ── ADDITIONAL REAL ESTATE ─────────────────────────────────────────────────
    {
        "id": "ARRIVED_HOMES",
        "name": "Arrived Homes Fractional Rental Properties",
        "category": "Real Estate",
        "subcategory": "Residential Rental",
        "chain": "Ethereum",
        "protocol": "Arrived Homes",
        "token_symbol": "ARVD",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 7.2,
        "risk_score": 5,
        "liquidity_score": 4,
        "regulatory_score": 8,
        "min_investment_usd": 100,
        "inception_date": "2021-09-01",
        "description": "Amazon-backed fractional single-family and vacation rental properties from $100. $100M+ in properties. Quarterly dividends, SEC-qualified.",
        "tags": ["retail", "real-estate", "residential", "rental-income", "fractional", "amazon-backed", "vacation-rental", "sec"],
    },
    {
        "id": "ROOFSTOCK_ONCHAIN",
        "name": "Roofstock onChain Tokenized Single-Family Rentals",
        "category": "Real Estate",
        "subcategory": "Residential Rental",
        "chain": "Ethereum",
        "protocol": "Roofstock",
        "token_symbol": "RST",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 6.8,
        "risk_score": 5,
        "liquidity_score": 4,
        "regulatory_score": 8,
        "min_investment_usd": 1_000,
        "inception_date": "2022-11-01",
        "description": "Full property ownership via NFT. Single-family rental homes deeded to LLC, transferred via NFT sale. First end-to-end tokenized home purchase ever.",
        "tags": ["institutional", "real-estate", "residential", "single-family", "nft-deed", "full-ownership"],
    },
    {
        "id": "HOMEBASE_SOL",
        "name": "Homebase Tokenized Real Estate on Solana",
        "category": "Real Estate",
        "subcategory": "Residential",
        "chain": "Solana",
        "protocol": "Homebase",
        "token_symbol": "HOME",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 7.0,
        "risk_score": 6,
        "liquidity_score": 5,
        "regulatory_score": 7,
        "min_investment_usd": 100,
        "inception_date": "2022-08-01",
        "description": "Solana-native fractional real estate from $100. US residential properties in Sunbelt markets. Rental income paid in USDC with weekly distributions.",
        "tags": ["retail", "real-estate", "residential", "solana", "usdc-yield", "sunbelt", "fractional"],
    },
    {
        "id": "REPUBLIC_RE",
        "name": "Republic Real Estate Tokenized Properties",
        "category": "Real Estate",
        "subcategory": "Commercial / Residential",
        "chain": "Ethereum",
        "protocol": "Republic",
        "token_symbol": "RNT",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 8.0,
        "risk_score": 6,
        "liquidity_score": 4,
        "regulatory_score": 8,
        "min_investment_usd": 1_000,
        "inception_date": "2020-07-01",
        "description": "Republic's Reg A+ and Reg D tokenized real estate. Mixed US commercial and residential properties. $2B+ raised across all Republic verticals.",
        "tags": ["retail", "real-estate", "commercial", "residential", "reg-a", "reg-d", "republic"],
    },
    {
        "id": "VESTA_EQUITY",
        "name": "Vesta Equity Tokenized Home Equity",
        "category": "Real Estate",
        "subcategory": "Home Equity",
        "chain": "Ethereum",
        "protocol": "Vesta Equity",
        "token_symbol": "VSTA",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 9.0,
        "risk_score": 6,
        "liquidity_score": 3,
        "regulatory_score": 7,
        "min_investment_usd": 1_000,
        "inception_date": "2022-01-01",
        "description": "Tokenized home equity agreements. Homeowners monetize equity with no monthly payments; investors receive appreciation share upon sale.",
        "tags": ["retail", "real-estate", "home-equity", "appreciation", "alternative-mortgage"],
    },
    {
        "id": "REALBLOCKS",
        "name": "RealBlocks Institutional Real Estate",
        "category": "Real Estate",
        "subcategory": "Institutional Commercial",
        "chain": "Ethereum",
        "protocol": "RealBlocks",
        "token_symbol": "RBLX",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 8.5,
        "risk_score": 5,
        "liquidity_score": 5,
        "regulatory_score": 8,
        "min_investment_usd": 10_000,
        "inception_date": "2019-01-01",
        "description": "Institutional tokenized real estate fund access platform. Connects accredited investors to top-tier commercial real estate managers globally.",
        "tags": ["institutional", "real-estate", "commercial", "fund-access", "accredited", "global"],
    },
    {
        "id": "REALT_EUROPE",
        "name": "RealT European Tokenized Properties",
        "category": "Real Estate",
        "subcategory": "European Residential",
        "chain": "Gnosis / Ethereum",
        "protocol": "RealT",
        "token_symbol": "REALT-EU",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 7.5,
        "risk_score": 5,
        "liquidity_score": 4,
        "regulatory_score": 8,
        "min_investment_usd": 50,
        "inception_date": "2023-01-01",
        "description": "RealT's European expansion: tokenized residential properties in France, Germany, Spain. MiCA-compliant structure. Yield paid in xDAI.",
        "tags": ["retail", "real-estate", "residential", "europe", "gnosis", "mica", "xdai-yield"],
    },

    # ── WISDOMTREE — Multi-chain tokenized funds ───────────────────────────────
    {
        "id": "WISDOMTREE_GOLD",
        "name": "WisdomTree Tokenized Gold",
        "category": "Commodities",
        "subcategory": "Gold",
        "chain": "Stellar / Ethereum",
        "protocol": "WisdomTree Prime",
        "token_symbol": "WTGOLD",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 0.0,
        "risk_score": 2,
        "liquidity_score": 7,
        "regulatory_score": 9,
        "min_investment_usd": 1,
        "inception_date": "2023-05-01",
        "description": "WisdomTree's tokenized physical gold on Stellar and Ethereum. $100B+ AUM manager. App-based, SEC-reviewed, audited vaults.",
        "tags": ["retail", "gold", "commodity", "stellar", "wisdomtree", "sec-reviewed", "app-native"],
    },
    # ── USUAL PROTOCOL — USD0 T-bill backed stablecoin ───────────────────────
    {
        "id": "USUAL_USD0",
        "name": "Usual Protocol USD0 — Tokenized Treasury Stablecoin",
        "category": "Government Bonds",
        "subcategory": "Yield Stablecoin",
        "chain": "Ethereum",
        "protocol": "Usual Protocol",
        "token_symbol": "USD0",
        "coingecko_id": "usual-usd",
        "defillama_slug": "usual",
        "expected_yield_pct": 4.50,
        "risk_score": 2,
        "liquidity_score": 9,
        "regulatory_score": 8,
        "min_investment_usd": 1,
        "inception_date": "2024-08-01",
        "description": "USD0 stablecoin backed 1:1 by BUIDL (BlackRock T-bill fund). Usual token holders earn yield from treasury portfolio. TVL $1B+. MiCA-eligible structure.",
        "tags": ["retail", "stablecoin", "treasury", "yield-bearing", "buidl-backed", "mica"],
    },
    # ── AGORA FINANCE — AUSD T-bill backed stablecoin ────────────────────────
    {
        "id": "AGORA_AUSD",
        "name": "Agora Finance AUSD — Regulated Treasury Dollar",
        "category": "Government Bonds",
        "subcategory": "Yield Stablecoin",
        "chain": "Ethereum",
        "protocol": "Agora Finance",
        "token_symbol": "AUSD",
        "coingecko_id": None,
        "defillama_slug": "agora-finance",
        "expected_yield_pct": 4.40,
        "risk_score": 2,
        "liquidity_score": 8,
        "regulatory_score": 8,
        "min_investment_usd": 1,
        "inception_date": "2024-06-01",
        "description": "Agora's AUSD is a regulated, institutionally-custodied stablecoin backed by US Treasuries and overnight repos. Dragonfly + White Star capital-backed.",
        "tags": ["retail", "stablecoin", "treasury", "yield-bearing", "institutional"],
    },
    # ── PENDLE FINANCE — Yield tokenization of RWA ───────────────────────────
    {
        "id": "PENDLE_PT_USDY",
        "name": "Pendle PT-USDY Fixed Yield",
        "category": "Government Bonds",
        "subcategory": "Fixed Yield Token",
        "chain": "Ethereum / Arbitrum",
        "protocol": "Pendle Finance",
        "token_symbol": "PT-USDY",
        "coingecko_id": "pendle",
        "defillama_slug": "pendle",
        "expected_yield_pct": 5.30,
        "risk_score": 2,
        "liquidity_score": 8,
        "regulatory_score": 7,
        "min_investment_usd": 1,
        "inception_date": "2023-11-01",
        "description": "Pendle Principal Token wrapping USDY (Ondo T-bill yield). Locks in fixed APY above spot USDY yield — buy at discount, redeem at par at maturity. Fully tradeable.",
        "tags": ["retail", "treasury", "yield-stripping", "fixed-rate", "pendle", "defi-native"],
    },
    {
        "id": "PENDLE_YT_USDY",
        "name": "Pendle YT-USDY Variable Yield Token",
        "category": "Government Bonds",
        "subcategory": "Yield Token",
        "chain": "Ethereum / Arbitrum",
        "protocol": "Pendle Finance",
        "token_symbol": "YT-USDY",
        "coingecko_id": "pendle",
        "defillama_slug": "pendle",
        "expected_yield_pct": 8.00,
        "risk_score": 4,
        "liquidity_score": 7,
        "regulatory_score": 7,
        "min_investment_usd": 10,
        "inception_date": "2023-11-01",
        "description": "Pendle Yield Token capturing all future USDY yield flows. Leveraged exposure to T-bill rates — benefits from rate hikes, loses on rate cuts. Speculative.",
        "tags": ["retail", "treasury", "yield-stripping", "speculative", "pendle", "defi-native"],
    },
    {
        "id": "PENDLE_PT_USDM",
        "name": "Pendle PT-USDM Fixed Rate",
        "category": "Government Bonds",
        "subcategory": "Fixed Yield Token",
        "chain": "Ethereum / Arbitrum / Optimism",
        "protocol": "Pendle Finance",
        "token_symbol": "PT-USDM",
        "coingecko_id": "pendle",
        "defillama_slug": "pendle",
        "expected_yield_pct": 5.10,
        "risk_score": 3,
        "liquidity_score": 8,
        "regulatory_score": 7,
        "min_investment_usd": 1,
        "inception_date": "2024-01-01",
        "description": "Pendle fixed-rate position on Mountain Protocol USDM. Maturity-based T-bill yield locked in. Multi-chain. Pendle TVL $3B+.",
        "tags": ["retail", "treasury", "yield-stripping", "fixed-rate", "pendle", "multi-chain"],
    },
    # ── HUMA FINANCE — PayFi/Trade Finance ───────────────────────────────────
    {
        "id": "HUMA_PAYFI",
        "name": "Huma Finance PayFi Protocol",
        "category": "Trade Finance",
        "subcategory": "Payment Financing",
        "chain": "Solana / Polygon",
        "protocol": "Huma Finance",
        "token_symbol": "HUMA",
        "coingecko_id": None,
        "defillama_slug": "huma-finance",
        "expected_yield_pct": 10.50,
        "risk_score": 5,
        "liquidity_score": 7,
        "regulatory_score": 8,
        "min_investment_usd": 100,
        "inception_date": "2023-06-01",
        "description": "PayFi protocol financing cross-border payments, remittances, and trade settlements. Real yield from payment networks (Arf, Bitso). $200M+ in real-world payment financing.",
        "tags": ["institutional", "trade-finance", "payfi", "payments", "remittance", "solana", "cross-border"],
    },
    # ── MORPHO BLUE — Institutional RWA Vaults ───────────────────────────────
    {
        "id": "MORPHO_STEAKHOUSE",
        "name": "Morpho Steakhouse USDC Vault",
        "category": "Government Bonds",
        "subcategory": "RWA Lending Vault",
        "chain": "Ethereum",
        "protocol": "Morpho / Steakhouse Financial",
        "token_symbol": "steakUSDC",
        "coingecko_id": None,
        "defillama_slug": "morpho",
        "expected_yield_pct": 5.20,
        "risk_score": 2,
        "liquidity_score": 8,
        "regulatory_score": 8,
        "min_investment_usd": 1,
        "inception_date": "2024-01-01",
        "description": "Morpho Blue vault managed by Steakhouse Financial. USDC earns T-bill yield via on-chain treasury collateral. $300M+ TVL. Risk-curated, daily withdrawals.",
        "tags": ["institutional", "treasury", "morpho", "vault", "usdc-yield", "defi-native", "steakhouse"],
    },
    {
        "id": "MORPHO_RE7",
        "name": "Morpho Re7 USDC Vault",
        "category": "Private Credit",
        "subcategory": "RWA Credit Vault",
        "chain": "Ethereum",
        "protocol": "Morpho / Re7 Capital",
        "token_symbol": "re7USDC",
        "coingecko_id": None,
        "defillama_slug": "morpho",
        "expected_yield_pct": 8.50,
        "risk_score": 4,
        "liquidity_score": 7,
        "regulatory_score": 8,
        "min_investment_usd": 1,
        "inception_date": "2024-03-01",
        "description": "Morpho vault curated by Re7 Capital targeting RWA-backed credit markets. Diversified across private credit protocols. Institutional risk management.",
        "tags": ["institutional", "private-credit", "morpho", "vault", "re7-capital", "defi-native"],
    },
    # ── SKY / MAKERDAO USDS — DAI Successor with enhanced yield ──────────────
    {
        "id": "SKY_USDS",
        "name": "Sky Protocol USDS (Upgraded DAI) + Sky Savings Rate",
        "category": "Government Bonds",
        "subcategory": "Yield Stablecoin",
        "chain": "Ethereum",
        "protocol": "Sky (formerly MakerDAO)",
        "token_symbol": "USDS",
        "coingecko_id": "usds",
        "defillama_slug": "sky",
        "expected_yield_pct": 4.75,
        "risk_score": 2,
        "liquidity_score": 10,
        "regulatory_score": 8,
        "min_investment_usd": 1,
        "inception_date": "2024-08-01",
        "description": "MakerDAO's rebrand to Sky protocol. USDS replaces DAI with native 4.75% Sky Savings Rate (SSR). Backed by BUIDL + real-world assets. $5B+ DAI-equivalent circulating.",
        "tags": ["retail", "stablecoin", "yield-bearing", "sky", "makerdao", "dai-successor", "rwa-backed"],
    },
    # ── NOBLE — Cosmos T-bill infrastructure ──────────────────────────────────
    {
        "id": "NOBLE_TBILL",
        "name": "Noble Protocol Tokenized T-Bills on Cosmos",
        "category": "Government Bonds",
        "subcategory": "US Treasury",
        "chain": "Noble",
        "protocol": "Noble / Ondo",
        "token_symbol": "USDY-COSMOS",
        "coingecko_id": None,
        "defillama_slug": "noble",
        "expected_yield_pct": 4.250,
        "risk_score": 2,
        "liquidity_score": 7,
        "regulatory_score": 8,
        "min_investment_usd": 500,
        "inception_date": "2024-04-01",
        "description": "Noble is the Cosmos chain for native asset issuance. Ondo USDY and tokenized T-bills flow through Noble to 40+ IBC-connected chains (Osmosis, dYdX, Celestia).",
        "tags": ["institutional", "treasury", "cosmos", "ibc", "noble", "cross-chain", "ondo"],
    },
    # ── KAMINO FINANCE — Solana yield with T-bill backing ─────────────────────
    {
        "id": "KAMINO_USDC",
        "name": "Kamino Finance USDC Yield Vault",
        "category": "Government Bonds",
        "subcategory": "Yield Vault",
        "chain": "Solana",
        "protocol": "Kamino Finance",
        "token_symbol": "kUSDC",
        "coingecko_id": None,
        "defillama_slug": "kamino",
        "expected_yield_pct": 6.50,
        "risk_score": 3,
        "liquidity_score": 9,
        "regulatory_score": 7,
        "min_investment_usd": 1,
        "inception_date": "2023-08-01",
        "description": "Kamino's leading Solana lending protocol. kUSDC earns from lending rates backed by T-bill collateral. $1B+ TVL. Auto-compounding USDC yield on Solana's fastest DEX ecosystem.",
        "tags": ["retail", "yield-vault", "solana", "usdc-yield", "auto-compound", "defi-native"],
    },
    # ── JPMORGAN KINEXYS — Institutional tokenized repo ──────────────────────
    {
        "id": "JPM_KINEXYS",
        "name": "JPMorgan Kinexys Digital Tokenized Repo",
        "category": "Government Bonds",
        "subcategory": "Institutional Repo",
        "chain": "Kinexys",
        "protocol": "JPMorgan / Kinexys",
        "token_symbol": "JPM-REPO",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 4.30,
        "risk_score": 1,
        "liquidity_score": 6,
        "regulatory_score": 10,
        "min_investment_usd": 1_000_000,
        "inception_date": "2023-01-01",
        "description": "JPMorgan Kinexys (formerly Onyx) tokenized intraday repo on private EVM. $1T+ in daily transaction volume. Used by Goldman Sachs, BNY Mellon, BlackRock for institutional repo settlement.",
        "tags": ["institutional", "repo", "jpmorgan", "kinexys", "private-chain", "t0-settlement", "qualified-purchaser"],
    },
    # ── HSBC ORION — Tokenized bonds ─────────────────────────────────────────
    {
        "id": "HSBC_ORION",
        "name": "HSBC Orion Tokenized Bonds",
        "category": "Government Bonds",
        "subcategory": "Digital Bond",
        "chain": "Ethereum",
        "protocol": "HSBC Orion",
        "token_symbol": "HSBC-BOND",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 4.60,
        "risk_score": 1,
        "liquidity_score": 5,
        "regulatory_score": 10,
        "min_investment_usd": 100_000,
        "inception_date": "2023-10-01",
        "description": "HSBC Orion platform for tokenized bond issuance. Launched Hong Kong Government tokenized green bonds ($750M), HSBC digital bond ($1B). FCA + HKMA regulated.",
        "tags": ["institutional", "digital-bond", "hsbc", "green-bond", "hkma", "fca-regulated", "sovereign"],
    },
    # ── UBS TOKENIZED MMF ─────────────────────────────────────────────────────
    {
        "id": "UBS_MMF_TOKEN",
        "name": "UBS Tokenized Money Market Fund",
        "category": "Government Bonds",
        "subcategory": "Money Market",
        "chain": "Ethereum",
        "protocol": "UBS / Chainlink CCIP",
        "token_symbol": "UBS-MMF",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 4.150,
        "risk_score": 1,
        "liquidity_score": 6,
        "regulatory_score": 10,
        "min_investment_usd": 500_000,
        "inception_date": "2024-02-01",
        "description": "UBS Asset Management tokenized MMF on Ethereum using Chainlink CCIP for cross-chain transfers. Part of Project Guardian (MAS Singapore). $3.6T AUM manager.",
        "tags": ["institutional", "money-market", "ubs", "chainlink-ccip", "mas-singapore", "project-guardian", "accredited"],
    },
    # ── CANTON NETWORK — Goldman Sachs GS DAP / DTCC Tokenized Treasuries ──────
    {
        "id": "CANTON_GS_DAP",
        "name": "Canton Network GS DAP Tokenized Government Securities",
        "category": "Government Bonds",
        "subcategory": "Institutional Repo / MMF",
        "chain": "Canton Network",
        "protocol": "Goldman Sachs / Digital Asset",
        "token_symbol": "GS-DAP",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 4.50,
        "risk_score": 1,
        "liquidity_score": 5,
        "regulatory_score": 10,
        "min_investment_usd": 5_000_000,
        "inception_date": "2025-06-24",
        "description": "Goldman Sachs GS DAP on Canton Network — purpose-built institutional privacy blockchain. DTCC tokenizing DTC-custodied US Treasuries on Canton (Dec 2025). BNY Mellon + GS first US tokenized MMF. $135M raised Jun 2025. GS DAP spinning out as independent company by mid-2026.",
        "tags": ["institutional", "treasury", "goldman-sachs", "canton-network", "dtcc", "bny-mellon", "digital-asset", "privacy-chain", "qualified-purchaser"],
    },
    # ── KINESIS MONEY — Gold + Silver with velocity yield ─────────────────────
    {
        "id": "KINESIS_KAU",
        "name": "Kinesis Gold (KAU) — Yield-Bearing Gold Token",
        "category": "Commodities",
        "subcategory": "Gold",
        "chain": "Ethereum",
        "protocol": "Kinesis Money",
        "token_symbol": "KAU",
        "coingecko_id": "kinesis-gold",
        "defillama_slug": None,
        "expected_yield_pct": 1.80,
        "risk_score": 3,
        "liquidity_score": 7,
        "regulatory_score": 8,
        "min_investment_usd": 1,
        "inception_date": "2019-11-01",
        "description": "1:1 gold-backed token earning velocity yield — holders receive a share of all transaction fees from the Kinesis monetary system. Unique: physical gold that generates income.",
        "tags": ["retail", "gold", "commodity", "yield-bearing", "velocity-yield", "physical-backed"],
    },
    {
        "id": "KINESIS_KAG",
        "name": "Kinesis Silver (KAG) — Yield-Bearing Silver Token",
        "category": "Commodities",
        "subcategory": "Silver",
        "chain": "Ethereum",
        "protocol": "Kinesis Money",
        "token_symbol": "KAG",
        "coingecko_id": "kinesis-silver",
        "defillama_slug": None,
        "expected_yield_pct": 2.20,
        "risk_score": 4,
        "liquidity_score": 6,
        "regulatory_score": 8,
        "min_investment_usd": 1,
        "inception_date": "2019-11-01",
        "description": "1:1 silver-backed token earning velocity yield from Kinesis network transaction fees. Higher yield than KAU due to greater trading velocity. Physical silver vaulted globally.",
        "tags": ["retail", "silver", "commodity", "yield-bearing", "velocity-yield", "physical-backed"],
    },
    # ── TERM FINANCE — Fixed-rate repo lending ────────────────────────────────
    {
        "id": "TERM_REPO",
        "name": "Term Finance Fixed-Rate Repo Protocol",
        "category": "Private Credit",
        "subcategory": "Fixed-Rate Repo",
        "chain": "Ethereum / Arbitrum",
        "protocol": "Term Finance",
        "token_symbol": "TERM",
        "coingecko_id": None,
        "defillama_slug": "term-finance",
        "expected_yield_pct": 9.00,
        "risk_score": 4,
        "liquidity_score": 7,
        "regulatory_score": 7,
        "min_investment_usd": 1_000,
        "inception_date": "2023-05-01",
        "description": "Fixed-rate, fixed-term repo protocol on Ethereum. Borrowers post USDC/wBTC/stETH collateral, lenders earn fixed rate. No duration mismatch. IOSG + Electric Capital backed.",
        "tags": ["institutional", "private-credit", "fixed-rate", "repo", "overcollateralized", "defi-native"],
    },
    # ── NOTIONAL FINANCE v3 — Fixed rate lending ──────────────────────────────
    {
        "id": "NOTIONAL_V3",
        "name": "Notional Finance v3 Fixed Rate Lending",
        "category": "Private Credit",
        "subcategory": "Fixed Rate",
        "chain": "Arbitrum",
        "protocol": "Notional Finance",
        "token_symbol": "NOTE",
        "coingecko_id": "notional-finance",
        "defillama_slug": "notional",
        "expected_yield_pct": 8.00,
        "risk_score": 4,
        "liquidity_score": 7,
        "regulatory_score": 7,
        "min_investment_usd": 1,
        "inception_date": "2023-09-01",
        "description": "Fixed-rate lending and borrowing on Arbitrum. USDC/DAI/ETH at fixed rates up to 1 year. Leveraged vault strategies for enhanced yield. Paradigm-backed.",
        "tags": ["institutional", "private-credit", "fixed-rate", "lending", "arbitrum", "paradigm-backed"],
    },
    # ── SDX — SIX Digital Exchange, Switzerland DLT Act ─────────────────────
    {
        "id": "SDX_DIGITAL_BOND",
        "name": "SDX SIX Digital Exchange Tokenized Bonds",
        "category": "Government Bonds",
        "subcategory": "Digital Bond",
        "chain": "SDX",
        "protocol": "SIX Group / SDX",
        "token_symbol": "SDX-BOND",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 3.80,
        "risk_score": 1,
        "liquidity_score": 5,
        "regulatory_score": 10,
        "min_investment_usd": 500_000,
        "inception_date": "2021-11-01",
        "description": "SIX Digital Exchange — Switzerland DLT Act-regulated institutional bond exchange. UBS CHF 375M digital bond, World Bank digital bonds, T+0 atomic settlement. Integrated with SIX Swiss Exchange CSD. World's most advanced tokenization legal framework.",
        "tags": ["institutional", "digital-bond", "swiss", "sdx", "six-group", "ubs", "world-bank", "dlt-act", "t0-settlement", "csd", "qualified-purchaser"],
    },
    # ── SIEMENS DIGITAL BOND — First corporate digital bond on public chain ───
    {
        "id": "SIEMENS_BOND",
        "name": "Siemens AG €60M Digital Bond",
        "category": "Government Bonds",
        "subcategory": "Corporate Digital Bond",
        "chain": "Polygon",
        "protocol": "Siemens / DekaBank",
        "token_symbol": "SIE-BOND",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 4.10,
        "risk_score": 1,
        "liquidity_score": 4,
        "regulatory_score": 10,
        "min_investment_usd": 100_000,
        "inception_date": "2023-02-01",
        "description": "Siemens issued €60M 1-year digital bond on Polygon — first corporate bond on public blockchain under German Electronic Securities Act (eWpG). BaFin regulated, DekaBank custodian.",
        "tags": ["institutional", "corporate-bond", "polygon", "siemens", "bafin-regulated", "ewpg", "digital-bond"],
    },
    # ── PLUME NETWORK — Purpose-built RWA blockchain ─────────────────────────
    {
        "id": "PLUME_TBILL",
        "name": "Plume Network Tokenized Treasury (rTBILL)",
        "category": "Government Bonds",
        "subcategory": "US Treasury",
        "chain": "Plume",
        "protocol": "Plume Network / Nested Finance",
        "token_symbol": "rTBILL",
        "coingecko_id": None,
        "defillama_slug": "plume",
        "expected_yield_pct": 4.350,
        "risk_score": 3,
        "liquidity_score": 6,
        "regulatory_score": 7,
        "min_investment_usd": 1,
        "inception_date": "2025-06-05",
        "description": "Plume Genesis mainnet launched June 5, 2025 with 50+ protocols on day one including Morpho and Curve. First purpose-built RWA L1 blockchain. rTBILL is the native T-bill token. EVM-compatible, compliance-native.",
        "tags": ["retail", "treasury", "plume", "rwa-chain", "compliance-native", "evm", "morpho", "curve"],
    },
    {
        "id": "PLUME_RE",
        "name": "Plume Network Tokenized Real Estate",
        "category": "Real Estate",
        "subcategory": "Residential Rental",
        "chain": "Plume",
        "protocol": "Plume Network / RWA protocols",
        "token_symbol": "pRE",
        "coingecko_id": None,
        "defillama_slug": "plume",
        "expected_yield_pct": 8.00,
        "risk_score": 5,
        "liquidity_score": 5,
        "regulatory_score": 7,
        "min_investment_usd": 100,
        "inception_date": "2025-06-05",
        "description": "Real estate tokenization on Plume Network (mainnet June 2025) via OpenEden, Nest Credit and other Plume ecosystem protocols. 50+ protocols launched day one. Purpose-built compliance layer reduces legal overhead.",
        "tags": ["retail", "real-estate", "plume", "rwa-chain", "compliance-native"],
    },
    # ── MANTRA CHAIN — Dubai-licensed RWA appchain ─────────────────────────────
    {
        "id": "MANTRA_RWA",
        "name": "Mantra Chain Tokenized Real World Assets",
        "category": "Private Credit",
        "subcategory": "Institutional RWA",
        "chain": "Mantra",
        "protocol": "Mantra Chain / OM",
        "token_symbol": "OM",
        "coingecko_id": "mantra-dao",
        "defillama_slug": "mantra",
        "expected_yield_pct": 9.00,
        "risk_score": 4,
        "liquidity_score": 6,
        "regulatory_score": 9,
        "min_investment_usd": 1_000,
        "inception_date": "2024-07-01",
        "description": "Mantra is a purpose-built, licensed RWA blockchain (VARA Dubai). $1B+ in deals signed with MAG Group, Damac Properties, NEOM. Cosmos-based, IBC-connected.",
        "tags": ["institutional", "private-credit", "mantra", "dubai", "vara-licensed", "cosmos", "real-estate-deals"],
    },
    # ── SWARM MARKETS Additional Stocks ──────────────────────────────────────
    {
        "id": "SWARM_MSFT",
        "name": "Swarm Microsoft Stock Token",
        "category": "Tokenized Equities",
        "subcategory": "Single Stock",
        "chain": "Polygon",
        "protocol": "Swarm Markets",
        "token_symbol": "sMSFT",
        "coingecko_id": None,
        "defillama_slug": "swarm",
        "expected_yield_pct": 0.0,
        "risk_score": 5,
        "liquidity_score": 7,
        "regulatory_score": 8,
        "min_investment_usd": 1,
        "inception_date": "2022-03-01",
        "description": "Fully-backed tokenized MSFT shares on Polygon. BaFin-licensed. 24/7 trading. Largest market cap stock available in tokenized form on Swarm.",
        "tags": ["retail", "equities", "single-stock", "bafin", "germany", "swarm"],
    },
    {
        "id": "SWARM_NVDA",
        "name": "Swarm NVIDIA Stock Token",
        "category": "Tokenized Equities",
        "subcategory": "Single Stock",
        "chain": "Polygon",
        "protocol": "Swarm Markets",
        "token_symbol": "sNVDA",
        "coingecko_id": None,
        "defillama_slug": "swarm",
        "expected_yield_pct": 0.0,
        "risk_score": 8,
        "liquidity_score": 7,
        "regulatory_score": 8,
        "min_investment_usd": 1,
        "inception_date": "2022-06-01",
        "description": "Fully-backed tokenized NVDA shares. BaFin-licensed. Highest volatility tokenized stock (AI/GPU demand-driven). 24/7 trading on Polygon.",
        "tags": ["retail", "equities", "single-stock", "bafin", "germany", "swarm", "ai-exposure"],
    },
    # ── MAPLE FINANCE — New Pool Structures ──────────────────────────────────
    {
        "id": "MAPLE_BLUECHIP",
        "name": "Maple Finance Blue Chip Secured Lending",
        "category": "Private Credit",
        "subcategory": "Overcollateralized Secured",
        "chain": "Ethereum / Solana",
        "protocol": "Maple Finance",
        "token_symbol": "MPL",
        "coingecko_id": "maple",
        "defillama_slug": "maple",
        "expected_yield_pct": 7.50,
        "risk_score": 3,
        "liquidity_score": 8,
        "regulatory_score": 8,
        "min_investment_usd": 100_000,
        "inception_date": "2023-10-01",
        "description": "Maple's blue-chip secured lending pool. Over-collateralized loans to institutional crypto firms using BTC and ETH as collateral. Lower yield but substantially lower risk than unsecured pools.",
        "tags": ["institutional", "private-credit", "secured", "overcollateralized", "btc-collateral", "eth-collateral"],
    },
    # ── REPUBLIC NOTE — Revenue-share alternative investment ─────────────────
    {
        "id": "REPUBLIC_NOTE",
        "name": "Republic Note — Digital Revenue Share Security",
        "category": "Private Equity",
        "subcategory": "Revenue Share",
        "chain": "Ethereum",
        "protocol": "Republic",
        "token_symbol": "RNT",
        "coingecko_id": "republic-note",
        "defillama_slug": None,
        "expected_yield_pct": 12.0,
        "risk_score": 7,
        "liquidity_score": 4,
        "regulatory_score": 8,
        "min_investment_usd": 500,
        "inception_date": "2019-07-01",
        "description": "SEC Reg D compliant revenue-share note giving holders a share of Republic's deal fee revenue. Unique cash-flow instrument tied to Republic's investment banking activity.",
        "tags": ["retail", "private-equity", "revenue-share", "republic", "sec-reg-d", "alternative"],
    },
    # ── CLEARPOOL PRIME — Institutional prime brokerage pools ────────────────
    {
        "id": "CLEARPOOL_PRIME",
        "name": "Clearpool Prime Institutional Credit",
        "category": "Private Credit",
        "subcategory": "Prime Brokerage",
        "chain": "Ethereum / Arbitrum / Base",
        "protocol": "Clearpool",
        "token_symbol": "CPOOL",
        "coingecko_id": "clearpool",
        "defillama_slug": "clearpool",
        "expected_yield_pct": 11.00,
        "risk_score": 5,
        "liquidity_score": 7,
        "regulatory_score": 8,
        "min_investment_usd": 0,
        "inception_date": "2024-01-01",
        "description": "Clearpool Prime enables institutional prime brokerage on-chain. Borrowers: top market makers and trading firms. Lenders earn above-market yield with credit score transparency.",
        "tags": ["institutional", "private-credit", "prime-brokerage", "market-makers", "credit-scoring", "multi-chain"],
    },
    # ── ETHENA USDe — Synthetic Dollar (unique RWA-adjacent yield) ────────────
    {
        "id": "ETHENA_SUSDE",
        "name": "Ethena sUSDe — Staked Synthetic Dollar",
        "category": "Private Credit",
        "subcategory": "Synthetic Basis Yield",
        "chain": "Ethereum / Arbitrum / Mantle",
        "protocol": "Ethena",
        "token_symbol": "sUSDe",
        "coingecko_id": "ethena-staked-usde",
        "defillama_slug": "ethena",
        "expected_yield_pct": 11.00,
        "risk_score": 5,
        "liquidity_score": 9,
        "regulatory_score": 6,
        "min_investment_usd": 1,
        "inception_date": "2024-02-01",
        "description": "Ethena USDe delta-neutral synthetic dollar backed by stETH + short ETH perp. sUSDe earns staking + funding rate yield. $3B+ TVL. Not strictly RWA but captures real yield from crypto basis.",
        "tags": ["retail", "synthetic-yield", "basis-trade", "defi-native", "staked", "delta-neutral", "funding-rate"],
    },

    # ── WISDOMTREE_GOVT (original kept below this) ─────────────────────────────
    {
        "id": "WISDOMTREE_GOVT",
        "name": "WisdomTree Tokenized Short-Term Government Bonds",
        "category": "Government Bonds",
        "subcategory": "US Treasury",
        "chain": "Stellar / Ethereum",
        "protocol": "WisdomTree Prime",
        "token_symbol": "WTGOVI",
        "coingecko_id": None,
        "defillama_slug": None,
        "expected_yield_pct": 4.25,
        "risk_score": 1,
        "liquidity_score": 7,
        "regulatory_score": 9,
        "min_investment_usd": 1,
        "inception_date": "2023-05-01",
        "description": "WisdomTree's tokenized short-term government bond fund on Stellar and Ethereum. Daily yield accrual via WisdomTree Prime app.",
        "tags": ["retail", "treasury", "stellar", "wisdomtree", "sec-reviewed", "daily-yield"],
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# PORTFOLIO RISK TIERS
# Each tier: name, description, color, target_yield, max_drawdown, allocations
# allocations: {category: weight_pct} — must sum to 100
# ─────────────────────────────────────────────────────────────────────────────

PORTFOLIO_TIERS = {
    1: {
        "name": "Ultra-Conservative",
        "label": "Shield",
        "color": "#00D4FF",
        "icon": "🛡️",
        "target_yield_pct": 4.5,
        "max_drawdown_pct": 1.0,
        "volatility_pct": 0.5,
        "description": "Capital preservation above all. US government-backed assets only. Sleep well regardless of market conditions.",
        "investor_profile": "Retirees, family offices, institutional treasuries seeking risk-free on-chain yield.",
        "allocations": {
            "Government Bonds": 75,
            "Commodities":      15,
            "Private Credit":    8,
            "Trade Finance":     2,
        },
        "subcategory_bias": ["US Treasury", "Money Market", "Yield Stablecoin", "Gold"],
        "min_risk_score": 1,
        "max_risk_score": 3,
        "rebalance_frequency": "monthly",
    },
    2: {
        "name": "Conservative",
        "label": "Anchor",
        "color": "#34D399",
        "icon": "⚓",
        "target_yield_pct": 7.5,
        "max_drawdown_pct": 5.0,
        "volatility_pct": 2.0,
        "description": "Steady income with minimal downside. High-quality fixed income plus real assets for inflation protection.",
        "investor_profile": "Financial advisors, HNW individuals, pension fund allocators.",
        "allocations": {
            "Government Bonds": 45,
            "Private Credit":   20,
            "Real Estate":      15,
            "Commodities":      15,
            "Carbon Credits":    3,
            "Trade Finance":     2,
        },
        "subcategory_bias": ["US Treasury", "Cash Management", "Residential Rental", "Gold", "Silver"],
        "min_risk_score": 1,
        "max_risk_score": 5,
        "rebalance_frequency": "monthly",
    },
    3: {
        "name": "Moderate",
        "label": "Balance",
        "color": "#FBBF24",
        "icon": "⚖️",
        "target_yield_pct": 11.0,
        "max_drawdown_pct": 15.0,
        "volatility_pct": 5.0,
        "description": "Diversified across all RWA categories. Optimal risk-adjusted return for most investors.",
        "investor_profile": "Sophisticated retail, crypto-native investors, family offices, robo-advisors.",
        "allocations": {
            "Government Bonds": 25,
            "Private Credit":   22,
            "Real Estate":      18,
            "Commodities":      10,
            "Infrastructure":    8,
            "Equities":          7,
            "Tokenized Equities": 5,   # NASDAQ/Dinari/Robinhood tokenized stocks
            "Carbon Credits":    3,
            "Trade Finance":     2,
        },
        "subcategory_bias": ["US Treasury", "Emerging Market Loans", "Residential Rental", "Gold", "Renewable Energy", "Tokenized Stocks"],
        "min_risk_score": 2,
        "max_risk_score": 7,
        "rebalance_frequency": "bi-weekly",
    },
    4: {
        "name": "Aggressive",
        "label": "Alpha",
        "color": "#F97316",
        "icon": "🔥",
        "target_yield_pct": 17.0,
        "max_drawdown_pct": 25.0,
        "volatility_pct": 10.0,
        "description": "Higher yield through selective exposure to private equity, high-yield credit, and development real estate.",
        "investor_profile": "Accredited investors, crypto funds, family offices with multi-year horizons.",
        "allocations": {
            "Private Credit":   28,
            "Real Estate":      18,
            "Private Equity":   15,
            "Government Bonds": 10,
            "Infrastructure":   10,
            "Equities":          7,
            "Tokenized Equities": 5,  # DEX/platform tokenized stocks (Dinari, Gains, Synthetix)
            "Carbon Credits":    4,
            "Art & Collectibles": 1,
            "Insurance":         2,
        },
        "subcategory_bias": ["High Yield", "Pre-IPO / Secondary", "Commercial", "Infrastructure Debt", "Tokenized Stocks"],
        "min_risk_score": 4,
        "max_risk_score": 8,
        "rebalance_frequency": "weekly",
    },
    5: {
        "name": "Ultra-Aggressive",
        "label": "Apex",
        "color": "#EF4444",
        "icon": "⚡",
        "target_yield_pct": 25.0,
        "max_drawdown_pct": 40.0,
        "volatility_pct": 20.0,
        "description": "Maximum return pursuit. Emerging market credit, distressed real estate, early-stage private equity, alternative RWAs.",
        "investor_profile": "Professional traders, crypto-native funds, ultra-HNW speculative allocation.",
        "allocations": {
            "Private Credit":   30,
            "Private Equity":   20,
            "Real Estate":      15,
            "Intellectual Property": 10,
            "Art & Collectibles": 8,
            "Carbon Credits":    7,
            "Infrastructure":    5,
            "Insurance":         3,
            "Trade Finance":     2,
        },
        "subcategory_bias": ["Emerging Market Loans", "Pre-IPO / Secondary", "Music Royalties", "Nature-Based", "Renewable Energy"],
        "min_risk_score": 5,
        "max_risk_score": 10,
        "rebalance_frequency": "daily",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# AI AGENT PROFILES
# Each agent: name, description, risk_tier, max_trade_size_pct, strategy
# ─────────────────────────────────────────────────────────────────────────────

AI_AGENTS = {
    "GUARDIAN": {
        "name": "Guardian AI",
        "description": "Ultra-conservative yield optimizer. Focuses on T-bill rotation and AAA credit quality.",
        "risk_tier": 1,
        "max_trade_size_pct": 5.0,
        "daily_loss_limit_pct": 0.5,
        "strategy": "yield_optimization",
        "rebalance_threshold_pct": 2.0,
        "color": "#00D4FF",
        "icon": "🛡️",
    },
    "NAVIGATOR": {
        "name": "Navigator AI",
        "description": "Conservative income generator. Balances T-bills, investment-grade credit, and real estate yield.",
        "risk_tier": 2,
        "max_trade_size_pct": 8.0,
        "daily_loss_limit_pct": 1.5,
        "strategy": "income_generation",
        "rebalance_threshold_pct": 3.0,
        "color": "#34D399",
        "icon": "⚓",
    },
    "HORIZON": {
        "name": "Horizon AI",
        "description": "Balanced portfolio manager. Multi-asset RWA diversification with MPT optimization.",
        "risk_tier": 3,
        "max_trade_size_pct": 10.0,
        "daily_loss_limit_pct": 3.0,
        "strategy": "mpt_balanced",
        "rebalance_threshold_pct": 5.0,
        "color": "#FBBF24",
        "icon": "⚖️",
    },
    "TITAN": {
        "name": "Titan AI",
        "description": "Aggressive alpha seeker. Targets high-yield private credit, PE, and arbitrage opportunities.",
        "risk_tier": 4,
        "max_trade_size_pct": 15.0,
        "daily_loss_limit_pct": 5.0,
        "strategy": "alpha_generation",
        "rebalance_threshold_pct": 8.0,
        "color": "#F97316",
        "icon": "🔥",
    },
    "APEX": {
        "name": "Apex AI",
        "description": "Maximum return hunter. Deploys across all RWA categories with dynamic risk sizing.",
        "risk_tier": 5,
        "max_trade_size_pct": 25.0,
        "daily_loss_limit_pct": 10.0,
        "strategy": "maximum_return",
        "rebalance_threshold_pct": 10.0,
        "color": "#EF4444",
        "icon": "⚡",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# DEFILLAMA PROTOCOL SLUGS (for TVL / yield data)
# ─────────────────────────────────────────────────────────────────────────────

DEFILLAMA_PROTOCOLS = [
    # ── Core RWA protocols ────────────────────────────────────────────────────
    "centrifuge", "maple", "goldfinch", "truefi", "ondo-finance",
    "makerdao", "sky",             # Sky = MakerDAO rebrand
    "backed-finance", "superstate", "mountain-protocol",
    "klimadao", "toucan", "credix", "polytrade", "nexus-mutual",
    "parcl", "tangible",
    # ── Avalanche ecosystem ───────────────────────────────────────────────────
    "spiko",
    # ── Base ecosystem ────────────────────────────────────────────────────────
    "dinari", "opentrade",
    # ── DEX tokenized stocks ──────────────────────────────────────────────────
    "gains-network", "synthetix",
    # ── Aptos ecosystem ───────────────────────────────────────────────────────
    "thala",
    # ── Sui ecosystem ─────────────────────────────────────────────────────────
    "bucket-protocol",
    # ── Additional core RWA ───────────────────────────────────────────────────
    "enzyme", "realtoken", "lofty",
    # ── New 2024-2026 protocols ───────────────────────────────────────────────
    "pendle",             # Yield tokenization — $3B+ TVL — wraps USDY, USDM, sUSDe
    "morpho",             # Morpho Blue — institutional RWA vaults (Steakhouse, Re7)
    "usual",              # Usual Protocol — USD0 backed by BUIDL
    "agora-finance",      # AUSD T-bill stablecoin
    "huma-finance",       # PayFi / trade finance protocol
    "kamino",             # Solana yield vaults with T-bill backing
    "ethena",             # sUSDe basis-trade yield ($3B+ TVL)
    "term-finance",       # Fixed-rate repo protocol
    "notional",           # Fixed rate lending v3 on Arbitrum
    "clearpool",          # Multi-chain institutional credit (already tracked)
    "hashnote",           # USYC T-bill token (already tracked)
    "plume",              # Plume Network RWA chain
    "mantra",             # Mantra Chain RWA appchain
    "noble",              # Noble Cosmos T-bill infrastructure
    "flowcarbon",         # Carbon credits
    "openeden",           # OpenEden TBILL vault (Moody's A-rated)
    "swarm",              # Swarm Markets tokenized stocks
    "agrotoken",          # Agricultural commodity tokens
    "kinesis",            # Gold/silver velocity yield tokens
    "matrixdock-stbt",    # Matrixdock STBT — first Asian T-bill token
    "propy",              # Propy RE title/escrow
    "maple-v2",           # Maple Finance v2 ($3.2B TVL)
    "backed-assets",      # Backed Finance ERC-20 ETFs
    "archax",             # UK FCA-regulated tokenized funds
    "midas-mtbill",       # Midas mTBILL tokenized T-bill
    "midas-mbasis",       # Midas mBASIS basis trade token
]

# ─────────────────────────────────────────────────────────────────────────────
# COINGECKO TOKEN IDS for price feeds
# ─────────────────────────────────────────────────────────────────────────────

COINGECKO_IDS = list(dict.fromkeys(
    a["coingecko_id"] for a in RWA_UNIVERSE if a.get("coingecko_id")
))

# ─────────────────────────────────────────────────────────────────────────────
# ASSET CATEGORY COLORS
# ─────────────────────────────────────────────────────────────────────────────

CATEGORY_COLORS = {
    "Government Bonds":     "#00D4FF",
    "Private Credit":       "#34D399",
    "Real Estate":          "#A78BFA",
    "Commodities":          "#FBBF24",
    "Equities":             "#F97316",
    "Infrastructure":       "#06B6D4",
    "Carbon Credits":       "#10B981",
    "Intellectual Property":"#EC4899",
    "Art & Collectibles":   "#8B5CF6",
    "Private Equity":       "#EF4444",
    "Insurance":            "#6366F1",
    "Trade Finance":        "#14B8A6",
    "Tokenized Equities":   "#FF6B35",   # NASDAQ / Robinhood / DEX tokenized stocks
}

# ─────────────────────────────────────────────────────────────────────────────
# CHAIN ECOSYSTEM MAP — all supported blockchains
# ─────────────────────────────────────────────────────────────────────────────

CHAIN_COLORS = {
    "Ethereum":     "#627EEA",
    "Polygon":      "#8247E5",
    "Solana":       "#9945FF",
    "Avalanche":    "#E84142",
    "Base":         "#0052FF",
    "Arbitrum":     "#28A0F0",
    "Optimism":     "#FF0420",
    "Gnosis":       "#04795B",
    "Hedera":       "#222222",
    "XRP Ledger":   "#346AA9",
    "Tezos":        "#2C7DF7",
    "Provenance":   "#6D28D9",
    "Aptos":        "#00C2CB",
    "Cardano":      "#0033AD",
    "Sui":          "#6FBCF0",
    "Stellar":      "#7D00FF",
    "Algorand":     "#00B4D8",
    "Tron":         "#FF0013",
    "BSC":          "#F3BA2F",
    "Multiple":     "#94A3B8",
    "Off-chain / Reg A+": "#64748B",
    # New chains — 2025/2026 RWA ecosystem expansion
    "Plume":        "#D4A843",   # gold — purpose-built RWA chain
    "Mantra":       "#C084FC",   # purple — Dubai-licensed Cosmos appchain
    "Noble":        "#38BDF8",   # sky blue — Cosmos T-bill infrastructure
    "TON":          "#0098EA",   # Telegram blue
    "ZKsync Era":   "#1755F4",   # ZK blue
    "Starknet":     "#EC796B",   # StarkNet coral
    "Linea":        "#61DFFF",   # Consensys teal
    "Mantle":       "#3CB290",   # Mantle teal
    "Kinexys":      "#003087",   # JPMorgan institutional dark blue
    "Centrifuge Chain": "#2E2D2D",
    "Canton Network": "#4A90D9",  # Goldman Sachs / Digital Asset institutional blue
    "Polymesh":     "#E5A50A",   # Polymath gold — regulated securities chain
    "SDX":          "#EF4444",   # SIX Digital Exchange red — Swiss DLT Act regulated
    "Berachain":    "#FFB92F",   # honey amber — Proof of Liquidity EVM chain
}

# ─────────────────────────────────────────────────────────────────────────────
# RISK SCORE LABELS
# ─────────────────────────────────────────────────────────────────────────────

RISK_LABELS = {
    1:  "AAA / Risk-Free",
    2:  "AA / Minimal Risk",
    3:  "A / Very Low Risk",
    4:  "BBB / Low Risk",
    5:  "BB / Moderate Risk",
    6:  "B / Medium-High Risk",
    7:  "CCC / High Risk",
    8:  "CC / Very High Risk",
    9:  "C / Extreme Risk",
    10: "D / Speculative",
}

# ─────────────────────────────────────────────────────────────────────────────
# ARBITRAGE THRESHOLDS
# ─────────────────────────────────────────────────────────────────────────────

ARB_MIN_YIELD_SPREAD_PCT    = 1.0   # minimum yield spread to flag arb opportunity
ARB_MIN_PRICE_SPREAD_PCT    = 0.5   # minimum price spread (vs NAV) to flag
ARB_STRONG_THRESHOLD_PCT    = 3.0   # strong arbitrage threshold
ARB_EXTREME_THRESHOLD_PCT   = 5.0   # extreme/exceptional arbitrage

# ─────────────────────────────────────────────────────────────────────────────
# ASSET MANAGEMENT FEES (basis points per year)
# Used by yield normalization engine to compute Net APY
# Source: protocol docs / fund prospectuses (March 2026)
# ─────────────────────────────────────────────────────────────────────────────

ASSET_FEE_BPS: dict = {
    # Government Bonds — T-bill / money market products
    "BUIDL":        15,   # BlackRock 0.15% mgmt fee
    "BENJI":        20,   # Franklin Templeton 0.20% mgmt fee
    "USTB":         15,   # Superstate 0.15% mgmt fee
    "TBILL":        50,   # OpenEden 0.50% (vault fee included)
    "USDY":          0,   # Ondo USDY — no explicit fee; yield is net
    "OUSG":         15,   # Ondo OUSG 0.15% mgmt fee
    "STBT":         30,   # Matrixdock STBT 0.30%
    "USYC":         50,   # Hashnote USYC 0.50%
    "USCC":         20,   # CF Benchmarks 0.20%
    "NOBLE-TBILL":  10,   # Noble T-bill 0.10%
    "rTBILL":       25,   # Ondo/Plume rTBILL 0.25%
    "PT-USDY":       0,   # Pendle PT — fee baked in discount
    "PT-USDM":       0,   # Pendle PT — fee baked in discount
    "USYIELD":      30,   # 0.30%
    "BUIDL-BR":     15,
    "mTBILL":       15,   # Midas mTBILL 0.15%
    "mBASIS":       50,   # Midas mBASIS 0.50%
    "AUSD":         20,   # Agora AUSD 0.20%
    "SPIKO-TBILL":  10,   # Spiko 0.10%
    "ARCHI-TBILL":  15,   # Archax 0.15%
    # Private Credit
    "MPL":         100,   # Maple 1.00% mgmt fee (on deployed capital)
    "CLPOOL":      150,   # Clearpool ~1.5% protocol fee
    "GFI":         150,   # Goldfinch ~1.5%
    "TRU":         100,   # TrueFi ~1.0%
    "CFG":         100,   # Centrifuge ~1.0%
    "HUMA":         80,   # Huma Finance 0.80%
    "CREDIX":      150,   # Credix ~1.5% EM premium
    "POLYTRADE":   100,   # Polytrade 1.0%
    "MORPHO-RE7":   75,   # Morpho Re7 vault 0.75%
    "MORPHO-STEAK": 50,   # Steakhouse vault 0.50%
    # Real Estate
    "REALT":       200,   # RealT ~2% fees total
    "LOFTY":       150,   # Lofty 1.5%
    "PARCL":        50,   # Parcl 0.5%
    "PROPY":       100,   # Propy 1.0%
    "TANGIBLE":    150,   # Tangible 1.5%
    "MANTRA-RE":   100,   # Mantra RE 1.0%
    "PLUME-RE":    100,   # Plume RE 1.0%
    # Commodities (spot — no mgmt fee beyond spread)
    "PAXG":         20,   # Paxos PAXG 0.20% custody fee
    "XAUT":         15,   # Tether Gold 0.15%
    "KAU":          25,   # Kinesis KAU 0.25% velocity fee
    "KAG":          25,   # Kinesis KAG 0.25%
    "XAUm":         20,   # Aurus Gold 0.20%
    "CXAU":         20,
    "MCO2":          5,   # Moss MCO2 minimal fee
    "BCT":           5,   # Toucan BCT minimal fee
    # Tokenized Equities / Synthetic
    "ONDO-GM":      15,   # Ondo Global Markets 0.15%
    "DSHARES":      25,   # Dinari dShares 0.25%
    "BACKED-CSPX":  15,   # Backed Finance 0.15%
    "SWARM-TSLA":   25,   # Swarm Markets 0.25%
    "SWARM-AAPL":   25,
    "SWARM-MSFT":   25,
    "SWARM-NVDA":   25,
    "BACKED-NASDAQ":15,
    "ROBINHOOD-RWA":15,
}

# Default fees by category (fallback when asset not in above dict)
_CATEGORY_FEE_BPS_DEFAULT: dict = {
    "Government Bonds":     20,
    "Private Credit":      100,
    "Real Estate":         150,
    "Commodities":          20,
    "Tokenized Equities":   20,
    "Equities":             20,
    "Private Equity":      200,
    "Carbon Credits":       20,
    "Intellectual Property":150,
    "Art & Collectibles":  200,
    "Infrastructure":      100,
    "Insurance":           100,
    "Trade Finance":        80,
}

def get_asset_fee_bps(asset_id: str, category: str = "") -> int:
    """Return management fee in basis points for a given asset."""
    return ASSET_FEE_BPS.get(
        asset_id,
        _CATEGORY_FEE_BPS_DEFAULT.get(category, 25)
    )


# ─────────────────────────────────────────────────────────────────────────────
# ASSET DURATION (years) — for interest rate risk / DV01 calculations
# Duration = price sensitivity to a 1% move in yields
# Money market (<90d): ~0.08y | Short (<1y): 0.25-0.75y | Medium (2-5y): 2-5y
# ─────────────────────────────────────────────────────────────────────────────

ASSET_DURATION_YEARS: dict = {
    # Government Bonds — money market (30-90 day bills)
    "BUIDL":        0.08,   # overnight repo / T-bills <30d
    "BENJI":        0.08,   # overnight repo + short bills
    "USTB":         0.10,   # short-duration (0-3 month)
    "TBILL":        0.08,   # T-bills <90 day
    "USDY":         0.17,   # 1-2 month bills (day 60 avg)
    "OUSG":         0.15,   # short US Treasuries
    "STBT":         0.17,   # STBT short-term bills
    "USYC":         0.08,   # overnight USDC / T-bill
    "USCC":         0.25,   # 0-6 month composite
    "NOBLE-TBILL":  0.08,
    "rTBILL":       0.17,
    "PT-USDY":      0.50,   # fixed term Pendle PT
    "PT-USDM":      0.50,
    "mTBILL":       0.08,
    "mBASIS":       0.10,
    "AUSD":         0.08,
    "SPIKO-TBILL":  0.08,
    "ARCHI-TBILL":  0.17,
    # Private Credit — typical loan tenor 6-36 months
    "MPL":          1.50,
    "CLPOOL":       0.75,   # shorter tenor clearpool
    "GFI":          2.00,   # EM credit 2yr avg
    "TRU":          1.00,
    "CFG":          2.00,   # Centrifuge pools vary; avg ~2yr
    "HUMA":         0.50,   # PayFi — short receivables
    "CREDIX":       2.00,
    "POLYTRADE":    0.25,   # trade finance — 60-90d
    "MORPHO-RE7":   0.50,
    "MORPHO-STEAK": 0.25,
    # Real Estate — long duration assets
    "REALT":        5.00,
    "LOFTY":        5.00,
    "PARCL":        3.00,   # derivatives-based, shorter effective duration
    "PROPY":        7.00,
    "TANGIBLE":     5.00,
    "MANTRA-RE":    5.00,
    "PLUME-RE":     5.00,
    # Commodities — zero interest rate duration (commodity price risk, not rate risk)
    "PAXG":         0.00,
    "XAUT":         0.00,
    "KAU":          0.00,
    "KAG":          0.00,
    "XAUm":         0.00,
    "CXAU":         0.00,
    # Carbon — effectively zero duration
    "MCO2":         0.00,
    "BCT":          0.00,
    # Tokenized Equities — equity duration (~15-20yr theoretical, but for rate sensitivity use ~5yr)
    "ONDO-GM":      5.00,
    "DSHARES":      5.00,
    "BACKED-CSPX":  5.00,
    "BACKED-NASDAQ":5.00,
}

# Default durations by category
_CATEGORY_DURATION_DEFAULT: dict = {
    "Government Bonds":      0.17,   # avg 2-month T-bill
    "Private Credit":        1.50,
    "Real Estate":           5.00,
    "Commodities":           0.00,
    "Tokenized Equities":    5.00,
    "Equities":              5.00,
    "Private Equity":        7.00,
    "Carbon Credits":        0.00,
    "Intellectual Property": 3.00,
    "Art & Collectibles":    0.00,
    "Infrastructure":        8.00,   # long-duration infra assets
    "Insurance":             2.00,
    "Trade Finance":         0.25,   # short receivables
}

def get_asset_duration(asset_id: str, category: str = "") -> float:
    """Return effective duration in years for a given asset."""
    return ASSET_DURATION_YEARS.get(
        asset_id,
        _CATEGORY_DURATION_DEFAULT.get(category, 1.0)
    )


# ─────────────────────────────────────────────────────────────────────────────
# ASSET LIQUIDITY METADATA
# redemption_days: business days to full exit at par / NAV
#   0 = instant DEX exit | 1 = T+1 | 7 = weekly | 30 = monthly
#   90 = quarterly | 180 = semi-annual | 365 = annual | 999 = effectively locked
# has_secondary: whether a liquid secondary market exists
# secondary_depth: qualitative secondary market depth (0=none, 1=thin, 2=moderate, 3=deep)
# ─────────────────────────────────────────────────────────────────────────────

ASSET_LIQUIDITY_META: dict = {
    # Government Bonds
    "BUIDL":        {"redemption_days": 1,   "has_secondary": False, "secondary_depth": 0},
    "BENJI":        {"redemption_days": 1,   "has_secondary": False, "secondary_depth": 0},
    "USTB":         {"redemption_days": 1,   "has_secondary": False, "secondary_depth": 0},
    "TBILL":        {"redemption_days": 1,   "has_secondary": True,  "secondary_depth": 1},
    "USDY":         {"redemption_days": 0,   "has_secondary": True,  "secondary_depth": 2},  # DEX pools
    "OUSG":         {"redemption_days": 1,   "has_secondary": True,  "secondary_depth": 2},
    "STBT":         {"redemption_days": 1,   "has_secondary": True,  "secondary_depth": 1},
    "USYC":         {"redemption_days": 1,   "has_secondary": False, "secondary_depth": 0},
    "USCC":         {"redemption_days": 1,   "has_secondary": False, "secondary_depth": 0},
    "NOBLE-TBILL":  {"redemption_days": 1,   "has_secondary": False, "secondary_depth": 0},
    "rTBILL":       {"redemption_days": 1,   "has_secondary": True,  "secondary_depth": 1},
    "PT-USDY":      {"redemption_days": 0,   "has_secondary": True,  "secondary_depth": 2},  # Pendle DEX
    "PT-USDM":      {"redemption_days": 0,   "has_secondary": True,  "secondary_depth": 1},
    "mTBILL":       {"redemption_days": 1,   "has_secondary": False, "secondary_depth": 0},
    # Private Credit
    "MPL":          {"redemption_days": 30,  "has_secondary": True,  "secondary_depth": 1},
    "CLPOOL":       {"redemption_days": 7,   "has_secondary": False, "secondary_depth": 0},
    "GFI":          {"redemption_days": 90,  "has_secondary": False, "secondary_depth": 0},
    "TRU":          {"redemption_days": 30,  "has_secondary": False, "secondary_depth": 0},
    "CFG":          {"redemption_days": 90,  "has_secondary": True,  "secondary_depth": 1},
    "HUMA":         {"redemption_days": 7,   "has_secondary": False, "secondary_depth": 0},
    "CREDIX":       {"redemption_days": 90,  "has_secondary": False, "secondary_depth": 0},
    "POLYTRADE":    {"redemption_days": 7,   "has_secondary": False, "secondary_depth": 0},
    "MORPHO-RE7":   {"redemption_days": 1,   "has_secondary": False, "secondary_depth": 0},
    "MORPHO-STEAK": {"redemption_days": 1,   "has_secondary": False, "secondary_depth": 0},
    # Real Estate
    "REALT":        {"redemption_days": 30,  "has_secondary": True,  "secondary_depth": 1},
    "LOFTY":        {"redemption_days": 1,   "has_secondary": True,  "secondary_depth": 2},  # marketplace
    "PARCL":        {"redemption_days": 0,   "has_secondary": True,  "secondary_depth": 2},  # DEX perps
    "PROPY":        {"redemption_days": 180, "has_secondary": False, "secondary_depth": 0},
    "TANGIBLE":     {"redemption_days": 30,  "has_secondary": True,  "secondary_depth": 1},
    "MANTRA-RE":    {"redemption_days": 30,  "has_secondary": False, "secondary_depth": 0},
    "PLUME-RE":     {"redemption_days": 30,  "has_secondary": False, "secondary_depth": 0},
    # Commodities — liquid DEX / exchange markets
    "PAXG":         {"redemption_days": 0,   "has_secondary": True,  "secondary_depth": 3},
    "XAUT":         {"redemption_days": 0,   "has_secondary": True,  "secondary_depth": 3},
    "KAU":          {"redemption_days": 1,   "has_secondary": True,  "secondary_depth": 2},
    "KAG":          {"redemption_days": 1,   "has_secondary": True,  "secondary_depth": 2},
    "XAUm":         {"redemption_days": 1,   "has_secondary": True,  "secondary_depth": 1},
    "MCO2":         {"redemption_days": 0,   "has_secondary": True,  "secondary_depth": 2},
    "BCT":          {"redemption_days": 0,   "has_secondary": True,  "secondary_depth": 2},
    # Tokenized Equities
    "ONDO-GM":      {"redemption_days": 1,   "has_secondary": False, "secondary_depth": 0},
    "DSHARES":      {"redemption_days": 1,   "has_secondary": True,  "secondary_depth": 1},
    "BACKED-CSPX":  {"redemption_days": 2,   "has_secondary": True,  "secondary_depth": 1},
    "BACKED-NASDAQ":{"redemption_days": 2,   "has_secondary": True,  "secondary_depth": 1},
    "SWARM-TSLA":   {"redemption_days": 2,   "has_secondary": True,  "secondary_depth": 1},
    "SWARM-AAPL":   {"redemption_days": 2,   "has_secondary": True,  "secondary_depth": 1},
    "SWARM-MSFT":   {"redemption_days": 2,   "has_secondary": True,  "secondary_depth": 1},
    "SWARM-NVDA":   {"redemption_days": 2,   "has_secondary": True,  "secondary_depth": 1},
    "ROBINHOOD-RWA":{"redemption_days": 1,   "has_secondary": False, "secondary_depth": 0},
}

# Default liquidity by category
_CATEGORY_LIQUIDITY_DEFAULT: dict = {
    "Government Bonds":      {"redemption_days": 1,   "has_secondary": False, "secondary_depth": 0},
    "Private Credit":        {"redemption_days": 60,  "has_secondary": False, "secondary_depth": 0},
    "Real Estate":           {"redemption_days": 90,  "has_secondary": False, "secondary_depth": 0},
    "Commodities":           {"redemption_days": 1,   "has_secondary": True,  "secondary_depth": 2},
    "Tokenized Equities":    {"redemption_days": 2,   "has_secondary": True,  "secondary_depth": 1},
    "Equities":              {"redemption_days": 2,   "has_secondary": True,  "secondary_depth": 1},
    "Private Equity":        {"redemption_days": 365, "has_secondary": False, "secondary_depth": 0},
    "Carbon Credits":        {"redemption_days": 0,   "has_secondary": True,  "secondary_depth": 2},
    "Intellectual Property": {"redemption_days": 180, "has_secondary": False, "secondary_depth": 0},
    "Art & Collectibles":    {"redemption_days": 180, "has_secondary": False, "secondary_depth": 0},
    "Infrastructure":        {"redemption_days": 365, "has_secondary": False, "secondary_depth": 0},
    "Insurance":             {"redemption_days": 90,  "has_secondary": False, "secondary_depth": 0},
    "Trade Finance":         {"redemption_days": 30,  "has_secondary": False, "secondary_depth": 0},
}

def get_asset_liquidity_meta(asset_id: str, category: str = "") -> dict:
    """Return liquidity metadata for a given asset."""
    return ASSET_LIQUIDITY_META.get(
        asset_id,
        _CATEGORY_LIQUIDITY_DEFAULT.get(category, {"redemption_days": 30, "has_secondary": False, "secondary_depth": 0})
    )

# Optional API keys for new data sources
KAITO_API_KEY    = _os.environ.get("RWA_KAITO_API_KEY")  # kaito.ai — social/narrative analytics


# ─────────────────────────────────────────────────────────────────────────────
# EXIT VELOCITY METADATA
# Captures lock-up terms, OTC availability, minimum exit size, and partial-exit
# capability per asset. Used to compute the Exit Velocity Score (0-100).
# ─────────────────────────────────────────────────────────────────────────────

ASSET_EXIT_VELOCITY_META: dict = {
    # Government Bonds
    "BUIDL":         {"lockup_days": 0,   "otc_available": True,  "min_exit_usd": 250_000, "partial_exit": False},
    "BENJI":         {"lockup_days": 0,   "otc_available": False, "min_exit_usd": 1,        "partial_exit": True},
    "OUSG":          {"lockup_days": 0,   "otc_available": True,  "min_exit_usd": 100_000,  "partial_exit": True},
    "USDY":          {"lockup_days": 0,   "otc_available": False, "min_exit_usd": 1,        "partial_exit": True},
    "USTB":          {"lockup_days": 0,   "otc_available": False, "min_exit_usd": 100_000,  "partial_exit": True},
    "USDM":          {"lockup_days": 0,   "otc_available": False, "min_exit_usd": 1,        "partial_exit": True},
    "STBT":          {"lockup_days": 0,   "otc_available": False, "min_exit_usd": 1_000,    "partial_exit": True},
    "TBILL":         {"lockup_days": 0,   "otc_available": False, "min_exit_usd": 1_000,    "partial_exit": True},
    "USYC":          {"lockup_days": 0,   "otc_available": False, "min_exit_usd": 100_000,  "partial_exit": True},
    "USCC":          {"lockup_days": 0,   "otc_available": False, "min_exit_usd": 100_000,  "partial_exit": True},
    "rTBILL":        {"lockup_days": 0,   "otc_available": False, "min_exit_usd": 1_000,    "partial_exit": True},
    "PT-USDY":       {"lockup_days": 0,   "otc_available": False, "min_exit_usd": 1,        "partial_exit": True},
    "PT-USDM":       {"lockup_days": 0,   "otc_available": False, "min_exit_usd": 1,        "partial_exit": True},
    "mTBILL":        {"lockup_days": 0,   "otc_available": False, "min_exit_usd": 1_000,    "partial_exit": True},
    "NOBLE-TBILL":   {"lockup_days": 0,   "otc_available": False, "min_exit_usd": 1_000,    "partial_exit": True},
    # Private Credit
    "MPL":           {"lockup_days": 30,  "otc_available": False, "min_exit_usd": 100_000,  "partial_exit": False},
    "CLPOOL":        {"lockup_days": 7,   "otc_available": False, "min_exit_usd": 10_000,   "partial_exit": True},
    "GFI":           {"lockup_days": 90,  "otc_available": False, "min_exit_usd": 10_000,   "partial_exit": False},
    "TRU":           {"lockup_days": 30,  "otc_available": False, "min_exit_usd": 10_000,   "partial_exit": False},
    "CFG":           {"lockup_days": 90,  "otc_available": True,  "min_exit_usd": 10_000,   "partial_exit": False},
    "HUMA":          {"lockup_days": 7,   "otc_available": False, "min_exit_usd": 1_000,    "partial_exit": True},
    "CREDIX":        {"lockup_days": 90,  "otc_available": False, "min_exit_usd": 50_000,   "partial_exit": False},
    "POLYTRADE":     {"lockup_days": 7,   "otc_available": False, "min_exit_usd": 5_000,    "partial_exit": True},
    "MORPHO-RE7":    {"lockup_days": 0,   "otc_available": False, "min_exit_usd": 1,        "partial_exit": True},
    "MORPHO-STEAK":  {"lockup_days": 0,   "otc_available": False, "min_exit_usd": 1,        "partial_exit": True},
    # Real Estate
    "REALT":         {"lockup_days": 0,   "otc_available": True,  "min_exit_usd": 50,       "partial_exit": True},
    "LOFTY":         {"lockup_days": 0,   "otc_available": True,  "min_exit_usd": 50,       "partial_exit": True},
    "PARCL":         {"lockup_days": 0,   "otc_available": False, "min_exit_usd": 1,        "partial_exit": True},
    "PROPY":         {"lockup_days": 180, "otc_available": False, "min_exit_usd": 10_000,   "partial_exit": False},
    "TANGIBLE":      {"lockup_days": 30,  "otc_available": True,  "min_exit_usd": 1_000,    "partial_exit": True},
    "MANTRA-RE":     {"lockup_days": 30,  "otc_available": False, "min_exit_usd": 5_000,    "partial_exit": True},
    "PLUME-RE":      {"lockup_days": 30,  "otc_available": False, "min_exit_usd": 5_000,    "partial_exit": True},
    # Commodities
    "PAXG":          {"lockup_days": 0,   "otc_available": True,  "min_exit_usd": 1,        "partial_exit": True},
    "XAUT":          {"lockup_days": 0,   "otc_available": True,  "min_exit_usd": 1,        "partial_exit": True},
    "KAU":           {"lockup_days": 0,   "otc_available": True,  "min_exit_usd": 1,        "partial_exit": True},
    "KAG":           {"lockup_days": 0,   "otc_available": True,  "min_exit_usd": 1,        "partial_exit": True},
    "MCO2":          {"lockup_days": 0,   "otc_available": False, "min_exit_usd": 1,        "partial_exit": True},
    "BCT":           {"lockup_days": 0,   "otc_available": False, "min_exit_usd": 1,        "partial_exit": True},
    # Tokenized Equities
    "ONDO-GM":       {"lockup_days": 0,   "otc_available": False, "min_exit_usd": 100,      "partial_exit": True},
    "DSHARES":       {"lockup_days": 0,   "otc_available": False, "min_exit_usd": 1,        "partial_exit": True},
    "BACKED-CSPX":   {"lockup_days": 0,   "otc_available": True,  "min_exit_usd": 5_000,    "partial_exit": True},
    "BACKED-NASDAQ": {"lockup_days": 0,   "otc_available": True,  "min_exit_usd": 5_000,    "partial_exit": True},
    "SWARM-TSLA":    {"lockup_days": 0,   "otc_available": False, "min_exit_usd": 1,        "partial_exit": True},
    "SWARM-AAPL":    {"lockup_days": 0,   "otc_available": False, "min_exit_usd": 1,        "partial_exit": True},
    "SWARM-MSFT":    {"lockup_days": 0,   "otc_available": False, "min_exit_usd": 1,        "partial_exit": True},
    "SWARM-NVDA":    {"lockup_days": 0,   "otc_available": False, "min_exit_usd": 1,        "partial_exit": True},
    "ROBINHOOD-RWA": {"lockup_days": 0,   "otc_available": False, "min_exit_usd": 1,        "partial_exit": True},
}

_CATEGORY_EXIT_VELOCITY_DEFAULT: dict = {
    "Government Bonds":   {"lockup_days": 0,   "otc_available": False, "min_exit_usd": 10_000,  "partial_exit": True},
    "Private Credit":     {"lockup_days": 60,  "otc_available": False, "min_exit_usd": 50_000,  "partial_exit": False},
    "Real Estate":        {"lockup_days": 90,  "otc_available": False, "min_exit_usd": 10_000,  "partial_exit": False},
    "Commodities":        {"lockup_days": 0,   "otc_available": True,  "min_exit_usd": 1,       "partial_exit": True},
    "Tokenized Equities": {"lockup_days": 0,   "otc_available": False, "min_exit_usd": 100,     "partial_exit": True},
    "Carbon Credits":     {"lockup_days": 0,   "otc_available": False, "min_exit_usd": 1,       "partial_exit": True},
    "Trade Finance":      {"lockup_days": 30,  "otc_available": False, "min_exit_usd": 10_000,  "partial_exit": False},
    "Infrastructure":     {"lockup_days": 365, "otc_available": False, "min_exit_usd": 100_000, "partial_exit": False},
    "Stablecoins":        {"lockup_days": 0,   "otc_available": True,  "min_exit_usd": 1,       "partial_exit": True},
}


def get_exit_velocity_score(asset_id: str, category: str = "") -> dict:
    """
    Compute Exit Velocity Score (0-100) — how quickly can you exit this position?

    Components:
      - Redemption speed (50%): 0d=100, T+1=90, 3d=80, weekly=65, monthly=40, quarterly=20, annual=5
      - Secondary market depth (25%): none=0, low=40, medium=75, high=100
      - Lock-up penalty (15%): none=100, 7d=70, 30d=40, 90d=20, 365d=5
      - Access options (10%): OTC + partial exit availability

    Returns dict with score, label, days_to_exit, and component breakdown.
    """
    liq_meta = get_asset_liquidity_meta(asset_id, category)
    ev_meta  = ASSET_EXIT_VELOCITY_META.get(
        asset_id,
        _CATEGORY_EXIT_VELOCITY_DEFAULT.get(
            category,
            {"lockup_days": 30, "otc_available": False, "min_exit_usd": 10_000, "partial_exit": False}
        )
    )

    red_days = liq_meta.get("redemption_days", 30)
    if red_days == 0:    red_score = 100
    elif red_days == 1:  red_score = 90
    elif red_days <= 3:  red_score = 80
    elif red_days <= 7:  red_score = 65
    elif red_days <= 30: red_score = 40
    elif red_days <= 90: red_score = 20
    else:                red_score = 5

    sec_depth = liq_meta.get("secondary_depth", 0)
    sec_score = {0: 0, 1: 40, 2: 75, 3: 100}.get(sec_depth, 0)

    lockup = ev_meta.get("lockup_days", 0)
    if lockup == 0:        lockup_score = 100
    elif lockup <= 7:      lockup_score = 70
    elif lockup <= 30:     lockup_score = 40
    elif lockup <= 90:     lockup_score = 20
    else:                  lockup_score = 5

    otc     = ev_meta.get("otc_available", False)
    partial = ev_meta.get("partial_exit", False)
    access_score = 50 + (30 if otc else 0) + (20 if partial else 0)

    composite = round(
        red_score * 0.50 + sec_score * 0.25 + lockup_score * 0.15 + access_score * 0.10, 1
    )
    composite = min(composite, 100.0)

    if composite >= 80:   label = "INSTANT"
    elif composite >= 60: label = "FAST"
    elif composite >= 40: label = "MODERATE"
    elif composite >= 20: label = "SLOW"
    else:                 label = "ILLIQUID"

    return {
        "score":         composite,
        "label":         label,
        "days_to_exit":  max(red_days, lockup),
        "lockup_days":   lockup,
        "otc_available": otc,
        "partial_exit":  partial,
        "min_exit_usd":  ev_meta.get("min_exit_usd", 0),
        "components": {
            "redemption_speed": red_score,
            "secondary_market": sec_score,
            "lockup_penalty":   lockup_score,
            "access_options":   access_score,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# ISSUER TRUST SCORECARD
# Transparency and trust metadata per asset: auditor, custodian,
# proof-of-reserve mechanism, NAV update frequency, CUSIP/ISIN.
# ─────────────────────────────────────────────────────────────────────────────

ASSET_TRUST_META: dict = {
    # Government Bonds — highest transparency
    "BUIDL":         {"auditor": "Deloitte",      "custodian": "BNY Mellon",       "proof_of_reserve": "manual_attestation", "nav_update_freq": "daily",     "cusip_isin": "US09260C1099", "jurisdiction": "USA"},
    "BENJI":         {"auditor": "PwC",            "custodian": "BNY Mellon",       "proof_of_reserve": "manual_attestation", "nav_update_freq": "daily",     "cusip_isin": "US35473P1012", "jurisdiction": "USA"},
    "OUSG":          {"auditor": "Deloitte",       "custodian": "Coinbase Custody", "proof_of_reserve": "chainlink",          "nav_update_freq": "daily",     "cusip_isin": "",             "jurisdiction": "USA"},
    "USDY":          {"auditor": "Withum",         "custodian": "Multiple",         "proof_of_reserve": "chainlink",          "nav_update_freq": "real_time", "cusip_isin": "",             "jurisdiction": "USA"},
    "USTB":          {"auditor": "Hassman",        "custodian": "Anchorage Digital","proof_of_reserve": "manual_attestation", "nav_update_freq": "daily",     "cusip_isin": "",             "jurisdiction": "USA"},
    "USDM":          {"auditor": "Grant Thornton", "custodian": "Multiple",         "proof_of_reserve": "chainlink",          "nav_update_freq": "real_time", "cusip_isin": "",             "jurisdiction": "BVI"},
    "STBT":          {"auditor": "None public",    "custodian": "Multiple",         "proof_of_reserve": "none",               "nav_update_freq": "daily",     "cusip_isin": "",             "jurisdiction": "Cayman"},
    "TBILL":         {"auditor": "None public",    "custodian": "Bank of China",    "proof_of_reserve": "none",               "nav_update_freq": "daily",     "cusip_isin": "",             "jurisdiction": "Hong Kong"},
    "USYC":          {"auditor": "Deloitte",       "custodian": "Copper.co",        "proof_of_reserve": "manual_attestation", "nav_update_freq": "daily",     "cusip_isin": "",             "jurisdiction": "USA"},
    "rTBILL":        {"auditor": "None public",    "custodian": "Multiple",         "proof_of_reserve": "chainlink",          "nav_update_freq": "daily",     "cusip_isin": "",             "jurisdiction": "BVI"},
    "mTBILL":        {"auditor": "Grant Thornton", "custodian": "Multiple",         "proof_of_reserve": "manual_attestation", "nav_update_freq": "daily",     "cusip_isin": "",             "jurisdiction": "Luxembourg"},
    "PT-USDY":       {"auditor": "Withum",         "custodian": "Pendle SC",        "proof_of_reserve": "on_chain",           "nav_update_freq": "real_time", "cusip_isin": "",             "jurisdiction": "USA"},
    # Private Credit — on-chain transparency but no traditional audits
    "MPL":           {"auditor": "None public",    "custodian": "Smart contracts",  "proof_of_reserve": "on_chain",           "nav_update_freq": "real_time", "cusip_isin": "",             "jurisdiction": "USA"},
    "CLPOOL":        {"auditor": "None public",    "custodian": "Smart contracts",  "proof_of_reserve": "on_chain",           "nav_update_freq": "real_time", "cusip_isin": "",             "jurisdiction": "Cayman"},
    "GFI":           {"auditor": "None public",    "custodian": "Smart contracts",  "proof_of_reserve": "on_chain",           "nav_update_freq": "real_time", "cusip_isin": "",             "jurisdiction": "Cayman"},
    "TRU":           {"auditor": "None public",    "custodian": "Smart contracts",  "proof_of_reserve": "on_chain",           "nav_update_freq": "real_time", "cusip_isin": "",             "jurisdiction": "USA"},
    "CFG":           {"auditor": "None public",    "custodian": "Smart contracts",  "proof_of_reserve": "on_chain",           "nav_update_freq": "real_time", "cusip_isin": "",             "jurisdiction": "USA"},
    "HUMA":          {"auditor": "None public",    "custodian": "Smart contracts",  "proof_of_reserve": "on_chain",           "nav_update_freq": "real_time", "cusip_isin": "",             "jurisdiction": "USA"},
    "MORPHO-RE7":    {"auditor": "None public",    "custodian": "Smart contracts",  "proof_of_reserve": "on_chain",           "nav_update_freq": "real_time", "cusip_isin": "",             "jurisdiction": "Decentralized"},
    "MORPHO-STEAK":  {"auditor": "None public",    "custodian": "Smart contracts",  "proof_of_reserve": "on_chain",           "nav_update_freq": "real_time", "cusip_isin": "",             "jurisdiction": "Decentralized"},
    # Commodities
    "PAXG":          {"auditor": "Withum",         "custodian": "Brinks",           "proof_of_reserve": "chainlink",          "nav_update_freq": "real_time", "cusip_isin": "",             "jurisdiction": "USA"},
    "XAUT":          {"auditor": "Armanino",       "custodian": "Tether Vault",     "proof_of_reserve": "manual_attestation", "nav_update_freq": "real_time", "cusip_isin": "",             "jurisdiction": "BVI"},
    "KAU":           {"auditor": "BDO",            "custodian": "Kinesis Vault",    "proof_of_reserve": "manual_attestation", "nav_update_freq": "real_time", "cusip_isin": "",             "jurisdiction": "Australia"},
    "KAG":           {"auditor": "BDO",            "custodian": "Kinesis Vault",    "proof_of_reserve": "manual_attestation", "nav_update_freq": "real_time", "cusip_isin": "",             "jurisdiction": "Australia"},
    "MCO2":          {"auditor": "South Pole",     "custodian": "Registry",         "proof_of_reserve": "manual_attestation", "nav_update_freq": "daily",     "cusip_isin": "",             "jurisdiction": "USA"},
    "BCT":           {"auditor": "Verra",          "custodian": "Registry",         "proof_of_reserve": "on_chain",           "nav_update_freq": "real_time", "cusip_isin": "",             "jurisdiction": "Decentralized"},
    # Real Estate
    "REALT":         {"auditor": "None public",    "custodian": "RealT LLC",        "proof_of_reserve": "none",               "nav_update_freq": "monthly",   "cusip_isin": "",             "jurisdiction": "USA"},
    "LOFTY":         {"auditor": "None public",    "custodian": "Lofty.ai",         "proof_of_reserve": "none",               "nav_update_freq": "monthly",   "cusip_isin": "",             "jurisdiction": "USA"},
    "PARCL":         {"auditor": "None public",    "custodian": "Smart contracts",  "proof_of_reserve": "on_chain",           "nav_update_freq": "real_time", "cusip_isin": "",             "jurisdiction": "Decentralized"},
    "TANGIBLE":      {"auditor": "None public",    "custodian": "Tangible Trust",   "proof_of_reserve": "manual_attestation", "nav_update_freq": "monthly",   "cusip_isin": "",             "jurisdiction": "UK"},
    # Tokenized Equities
    "ONDO-GM":       {"auditor": "Deloitte",       "custodian": "Coinbase Custody", "proof_of_reserve": "chainlink",          "nav_update_freq": "daily",     "cusip_isin": "",             "jurisdiction": "USA"},
    "DSHARES":       {"auditor": "None public",    "custodian": "Dinari",           "proof_of_reserve": "on_chain",           "nav_update_freq": "real_time", "cusip_isin": "",             "jurisdiction": "USA"},
    "BACKED-CSPX":   {"auditor": "PwC",            "custodian": "Backed Assets",    "proof_of_reserve": "manual_attestation", "nav_update_freq": "daily",     "cusip_isin": "CH1148653601", "jurisdiction": "Switzerland"},
    "BACKED-NASDAQ": {"auditor": "PwC",            "custodian": "Backed Assets",    "proof_of_reserve": "manual_attestation", "nav_update_freq": "daily",     "cusip_isin": "CH1148653619", "jurisdiction": "Switzerland"},
    "SWARM-TSLA":    {"auditor": "None public",    "custodian": "Swarm",            "proof_of_reserve": "on_chain",           "nav_update_freq": "real_time", "cusip_isin": "",             "jurisdiction": "Germany"},
}

_TRUST_TOP_AUDITORS = {"Deloitte", "PwC", "Ernst & Young", "KPMG", "Grant Thornton"}
_TRUST_MID_AUDITORS = {"Withum", "Armanino", "Hassman", "Mazars", "BDO", "South Pole", "Verra"}


def get_asset_trust_score(asset_id: str, category: str = "") -> dict:
    """
    Compute a 0-10 trust/transparency score for an RWA asset.

    Components:
      - Auditor quality   (0-3): Big4/GT=3, mid-tier=2, other known=1, none=0
      - Proof of reserve  (0-3): chainlink=3, on_chain=2.5, manual_attestation=1.5, none=0
      - NAV update freq   (0-2): real_time=2, daily=1.5, weekly=1, monthly=0.5
      - CUSIP/ISIN bonus  (0-1): 1 if regulated instrument identifier present

    Returns dict with trust_score (0-10) and full breakdown.
    """
    meta = ASSET_TRUST_META.get(asset_id, {})

    auditor      = meta.get("auditor", "None public")
    custodian    = meta.get("custodian", "Unknown")
    por          = meta.get("proof_of_reserve", "none")
    nav_freq     = meta.get("nav_update_freq", "monthly")
    cusip        = meta.get("cusip_isin", "")
    jurisdiction = meta.get("jurisdiction", "Unknown")

    if auditor in _TRUST_TOP_AUDITORS:   auditor_score = 3.0
    elif auditor in _TRUST_MID_AUDITORS: auditor_score = 2.0
    elif auditor != "None public":       auditor_score = 1.0
    else:                                auditor_score = 0.0

    por_score  = {"chainlink": 3.0, "on_chain": 2.5, "manual_attestation": 1.5, "none": 0.0}.get(por, 0.0)
    nav_score  = {"real_time": 2.0, "daily": 1.5, "weekly": 1.0, "monthly": 0.5}.get(nav_freq, 0.5)
    cusip_score= 1.0 if cusip else 0.0

    score = round(min(auditor_score + por_score + nav_score + cusip_score, 10.0), 1)

    if score >= 7:    trust_label = "EXCELLENT"
    elif score >= 5:  trust_label = "GOOD"
    elif score >= 3:  trust_label = "FAIR"
    elif score >= 1:  trust_label = "WEAK"
    else:             trust_label = "OPAQUE"

    return {
        "trust_score":      score,
        "trust_label":      trust_label,
        "auditor":          auditor,
        "custodian":        custodian,
        "proof_of_reserve": por,
        "nav_update_freq":  nav_freq,
        "cusip_isin":       cusip,
        "jurisdiction":     jurisdiction,
        "components": {
            "auditor":          auditor_score,
            "proof_of_reserve": por_score,
            "nav_frequency":    nav_score,
            "cusip_isin":       cusip_score,
        },
    }
