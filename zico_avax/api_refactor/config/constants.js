// Configurações da Rede Avalanche
const NETWORKS = {
  AVALANCHE: {
    chainId: 43114,
    name: 'Avalanche C-Chain',
    rpcUrl: process.env.RPC_URL_AVALANCHE || 'https://api.avax.network/ext/bc/C/rpc',
    explorer: 'https://snowtrace.io',
    nativeCurrency: {
      name: 'AVAX',
      symbol: 'AVAX',
      decimals: 18
    }
  },
  FUJI: {
    chainId: 43113,
    name: 'Avalanche Fuji Testnet',
    rpcUrl: process.env.RPC_URL_FUJI || 'https://api.avax-test.network/ext/bc/C/rpc',
    explorer: 'https://testnet.snowtrace.io',
    nativeCurrency: {
      name: 'AVAX',
      symbol: 'AVAX',
      decimals: 18
    }
  }
};

// Endereços dos Contratos Trader Joe
const TRADER_JOE = {
  ROUTER: process.env.TRADER_JOE_ROUTER || '0x60aE616a2155Ee3d9A68541Ba4544862310933d4',
  FACTORY: process.env.TRADER_JOE_FACTORY || '0x9Ad6C38BE94206cA50bb0d90783171662CD1e917',
  JOE_TOKEN: '0x6e84a6216eA6dACC71eE8E6b0a5B7322EEbC0fDd',
  WAVAX: '0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7'
};



// Tokens Comuns na Avalanche
const COMMON_TOKENS = {
  WAVAX: '0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7',
  USDC: '0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E',
  USDT: '0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7',
  DAI: '0xd586E7F844cEa2F87f50152665BCbc2C279D8d70',
  WETH: '0x49D5c2BdFfac6CE2BFdB6640F4F80f226bc10bAB',
  JOE: '0x6e84a6216eA6dACC71eE8E6b0a5B7322EEbC0fDd',

  LINK: '0x5947BB275c521040051D82396192181b413227A3',
  UNI: '0x8eBAf22B6F053dFFeaf46f4Dd9eFA95D89ba8580'
};

// Configurações de Slippage
const SLIPPAGE_OPTIONS = {
  LOW: 0.5,      // 0.5%
  MEDIUM: 1.0,   // 1.0%
  HIGH: 2.0,     // 2.0%
  VERY_HIGH: 5.0 // 5.0%
};

// Configurações de Gas
const GAS_SETTINGS = {
  DEFAULT_GAS_LIMIT: 300000,
  SWAP_GAS_LIMIT: 500000,
  APPROVE_GAS_LIMIT: 100000,
  MAX_PRIORITY_FEE: '2 gwei',
  MAX_FEE_PER_GAS: '50 gwei'
};

// URLs das APIs
const API_URLS = {
  TRADER_JOE: 'https://api.traderjoexyz.com',

  COINGECKO: 'https://api.coingecko.com/api/v3',
  SNOWTRACE: 'https://api.snowtrace.io/api'
};

// Configurações de Rate Limiting
const RATE_LIMIT = {
  WINDOW_MS: parseInt(process.env.RATE_LIMIT_WINDOW_MS) || 900000, // 15 minutos
  MAX_REQUESTS: parseInt(process.env.RATE_LIMIT_MAX_REQUESTS) || 100
};

// Configurações de Segurança
const SECURITY = {
  JWT_SECRET: process.env.JWT_SECRET || 'your-secret-key-here',
  SIGNATURE_EXPIRY: 5 * 60 * 1000, // 5 minutos
  MAX_AMOUNT: '1000000', // 1M AVAX
  MIN_AMOUNT: '0.000001' // 0.000001 AVAX
};

module.exports = {
  NETWORKS,
  TRADER_JOE,

  COMMON_TOKENS,
  SLIPPAGE_OPTIONS,
  GAS_SETTINGS,
  API_URLS,
  RATE_LIMIT,
  SECURITY
};
