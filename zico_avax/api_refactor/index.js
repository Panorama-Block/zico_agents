require('dotenv').config();
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const compression = require('compression');
const morgan = require('morgan');
const rateLimit = require('express-rate-limit');

// Importa rotas
const swapRoutes = require('./routes/swapRoutes');
const priceRoutes = require('./routes/priceRoutes');

// Importa configurações
const { NETWORKS, RATE_LIMIT, SECURITY } = require('./config/constants');

const app = express();
const port = process.env.PORT || 3001;

// Middleware de segurança
app.use(helmet({
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      styleSrc: ["'self'", "'unsafe-inline'"],
      scriptSrc: ["'self'"],
      imgSrc: ["'self'", "data:", "https:"],
    },
  },
  crossOriginEmbedderPolicy: false,
}));

// Middleware de CORS
app.use(cors({
  origin: process.env.NODE_ENV === 'production' 
    ? ['https://yourdomain.com'] // Substitua pelo seu domínio
    : true,
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization', 'X-Requested-With']
}));

// Middleware de compressão
app.use(compression());

// Middleware de logging
app.use(morgan('combined'));

// Middleware de parsing
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// Rate limiting global
const globalRateLimiter = rateLimit({
  windowMs: RATE_LIMIT.WINDOW_MS,
  max: RATE_LIMIT.MAX_REQUESTS,
  message: {
    error: 'Rate limit excedido',
    message: `Máximo de ${RATE_LIMIT.MAX_REQUESTS} requisições por ${RATE_LIMIT.WINDOW_MS / 1000} segundos`
  },
  standardHeaders: true,
  legacyHeaders: false,
  handler: (req, res) => {
    res.status(429).json({
      error: 'Rate limit excedido',
      message: `Máximo de ${RATE_LIMIT.MAX_REQUESTS} requisições por ${RATE_LIMIT.WINDOW_MS / 1000} segundos`,
      retryAfter: Math.ceil(RATE_LIMIT.WINDOW_MS / 1000)
    });
  }
});

app.use(globalRateLimiter);

// Middleware de validação de rede
app.use((req, res, next) => {
  // Adiciona informações da rede ao request
  req.network = NETWORKS.AVALANCHE;
  next();
});

// Rota de health check
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    network: NETWORKS.AVALANCHE.name,
    version: '1.0.0'
  });
});

// Rota de informações da API
app.get('/info', (req, res) => {
  res.json({
    name: 'Zico Swap API',
    description: 'API de Swap para Avalanche usando Trader Joe',
    version: '1.0.0',
    network: NETWORKS.AVALANCHE.name,
    chainId: NETWORKS.AVALANCHE.chainId,
    supportedProtocols: ['Trader Joe'],
    features: [
      'Swap de tokens',
      'Comparação de preços',
      'Execução de swaps',
      'Preços em tempo real',
      'Histórico de preços',
      'Tendências de mercado',
      'Cache inteligente',
      'Rate limiting',
      'Autenticação por assinatura'
    ],
    endpoints: {
      swap: '/swap',
      price: '/price',
      health: '/health',
      info: '/info'
    },
    documentation: 'https://github.com/your-repo/docs',
    support: 'support@yourdomain.com'
  });
});

// Rota de status da rede
app.get('/network/status', async (req, res) => {
  try {
    const { ethers } = require('ethers');
    const provider = new ethers.JsonRpcProvider(NETWORKS.AVALANCHE.rpcUrl);
    
    const [blockNumber, gasPrice, network] = await Promise.all([
      provider.getBlockNumber(),
      provider.getFeeData(),
      provider.getNetwork()
    ]);

    res.json({
      success: true,
      network: {
        name: NETWORKS.AVALANCHE.name,
        chainId: NETWORKS.AVALANCHE.chainId,
        rpcUrl: NETWORKS.AVALANCHE.rpcUrl,
        explorer: NETWORKS.AVALANCHE.explorer
      },
      status: {
        connected: true,
        blockNumber: blockNumber.toString(),
        gasPrice: gasPrice.gasPrice?.toString() || 'N/A',
        lastBlock: new Date().toISOString()
      },
      timestamp: Date.now()
    });
  } catch (error) {
    console.error('Erro ao verificar status da rede:', error);
    res.status(500).json({
      success: false,
      error: 'Erro ao verificar status da rede',
      details: error.message
    });
  }
});

// Rota de configurações
app.get('/config', (req, res) => {
  res.json({
    success: true,
    network: NETWORKS.AVALANCHE,
    rateLimit: RATE_LIMIT,
    security: {
      signatureExpiry: SECURITY.SIGNATURE_EXPIRY,
      maxAmount: SECURITY.MAX_AMOUNT,
      minAmount: SECURITY.MIN_AMOUNT
    },
    timestamp: Date.now()
  });
});

// Registra as rotas
app.use('/swap', swapRoutes);
app.use('/price', priceRoutes);

// Middleware de tratamento de erros
app.use((err, req, res, next) => {
  console.error('Erro não tratado:', err);
  
  res.status(err.status || 500).json({
    error: 'Erro interno do servidor',
    message: process.env.NODE_ENV === 'development' ? err.message : 'Algo deu errado',
    ...(process.env.NODE_ENV === 'development' && { stack: err.stack })
  });
});

// Middleware para rotas não encontradas
app.use('*', (req, res) => {
  res.status(404).json({
    error: 'Rota não encontrada',
    message: `A rota ${req.originalUrl} não existe`,
    availableRoutes: [
      'GET /health',
      'GET /info',
      'GET /network/status',
      'GET /config',
      'POST /swap/*',
      'GET /price/*'
    ]
  });
});

// Função para inicializar a API
async function initializeAPI() {
  try {
    // Verifica se as variáveis de ambiente necessárias estão configuradas
    const requiredEnvVars = [
      'RPC_URL_AVALANCHE'
    ];

    const missingVars = requiredEnvVars.filter(varName => !process.env[varName]);
    
    if (missingVars.length > 0) {
      console.warn('⚠️  Variáveis de ambiente ausentes:', missingVars.join(', '));
      console.warn('📝 Verifique o arquivo .env.example para configuração');
    }

    // Inicia o servidor
    app.listen(port, () => {
      console.log('🚀 Zico Swap API iniciada com sucesso!');
      console.log(`📍 Servidor rodando em http://localhost:${port}`);
      console.log(`🌐 Rede: ${NETWORKS.AVALANCHE.name} (Chain ID: ${NETWORKS.AVALANCHE.chainId})`);
      console.log(`🔗 RPC: ${NETWORKS.AVALANCHE.rpcUrl}`);
      console.log(`📊 Rate Limit: ${RATE_LIMIT.MAX_REQUESTS} requests/${RATE_LIMIT.WINDOW_MS / 1000}s`);
      console.log(`🔐 Modo: ${process.env.NODE_ENV || 'development'}`);
      console.log('');
      console.log('📋 Endpoints disponíveis:');
      console.log(`   Health Check: GET /health`);
      console.log(`   API Info: GET /info`);
      console.log(`   Network Status: GET /network/status`);
      console.log(`   Configuration: GET /config`);
      console.log(`   Swap Routes: POST /swap/*`);
      console.log(`   Price Routes: GET /price/*`);
      console.log('');
      console.log('💡 Para testar a API, use:');
      console.log(`   curl http://localhost:${port}/health`);
      console.log(`   curl http://localhost:${port}/info`);
    });

  } catch (error) {
    console.error('❌ Erro ao inicializar a API:', error);
    process.exit(1);
  }
}

// Função para graceful shutdown
function gracefulShutdown(signal) {
  console.log(`\n🛑 Recebido sinal ${signal}. Encerrando a API...`);
  
  process.exit(0);
}

// Listeners para graceful shutdown
process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
process.on('SIGINT', () => gracefulShutdown('SIGINT'));

// Tratamento de erros não capturados
process.on('uncaughtException', (error) => {
  console.error('❌ Erro não capturado:', error);
  process.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('❌ Promise rejeitada não tratada:', reason);
  process.exit(1);
});

// Inicializa a API
if (require.main === module) {
  initializeAPI();
}

module.exports = app;
