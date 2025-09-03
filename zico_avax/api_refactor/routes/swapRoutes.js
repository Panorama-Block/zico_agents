const express = require('express');
const { ethers } = require('ethers');
const TraderJoeService = require('../services/traderJoeService');

const PriceService = require('../services/priceService');
const { 
  verifySignature, 
  validateSwapParams, 
  createRateLimiter,
  validateNetwork,
  sanitizeInput
} = require('../middleware/auth');
const { NETWORKS, TRADER_JOE, COMMON_TOKENS, SLIPPAGE_OPTIONS } = require('../config/constants');

const router = express.Router();

// Rate limiting para rotas de swap
const swapRateLimiter = createRateLimiter(50, 15 * 60 * 1000); // 50 requests por 15 minutos

/**
 * @route POST /swap/price/traderjoe
 * @desc Obtém preço de swap no Trader Joe
 * @access Public (com assinatura)
 */
router.post('/price/traderjoe', 
  verifySignature, 
  swapRateLimiter,
  async (req, res) => {
    try {
      const { tokenIn, tokenOut, amountIn = '1000000000000000000' } = req.body;
      
      if (!tokenIn || !tokenOut) {
        return res.status(400).json({
          error: 'tokenIn e tokenOut são obrigatórios'
        });
      }

      const provider = new ethers.JsonRpcProvider(NETWORKS.AVALANCHE.rpcUrl);
      const traderJoeService = new TraderJoeService(provider);
      
      const price = await traderJoeService.getPrice(tokenIn, tokenOut, amountIn);
      
      res.json({
        success: true,
        protocol: 'Trader Joe',
        network: NETWORKS.AVALANCHE.name,
        data: price
      });
    } catch (error) {
      console.error('Erro ao obter preço Trader Joe:', error);
      res.status(500).json({
        error: 'Erro ao obter preço',
        details: error.message
      });
    }
  }
);



/**
 * @route POST /swap/price/compare
 * @desc Obtém preço de swap no Trader Joe (único protocolo suportado)
 * @access Public (com assinatura)
 */
router.post('/price/compare', 
  verifySignature, 
  swapRateLimiter,
  async (req, res) => {
    try {
      const { tokenIn, tokenOut, amountIn = '1000000000000000000' } = req.body;
      
      if (!tokenIn || !tokenOut) {
        return res.status(400).json({
          error: 'tokenIn e tokenOut são obrigatórios'
        });
      }

      const provider = new ethers.JsonRpcProvider(NETWORKS.AVALANCHE.rpcUrl);
      const traderJoeService = new TraderJoeService(provider);
      
      const price = await traderJoeService.getPrice(tokenIn, tokenOut, amountIn);

      res.json({
        success: true,
        network: NETWORKS.AVALANCHE.name,
        protocol: 'Trader Joe',
        data: price,
        note: 'Trader Joe é o único protocolo de swap suportado atualmente'
      });
    } catch (error) {
      console.error('Erro ao obter preço:', error);
      res.status(500).json({
        error: 'Erro ao obter preço',
        details: error.message
      });
    }
  }
);

/**
 * @route POST /swap/execute/traderjoe
 * @desc Executa swap no Trader Joe
 * @access Private (com wallet privada)
 */
router.post('/execute/traderjoe', 
  verifySignature, 
  validateSwapParams,
  swapRateLimiter,
  validateNetwork(NETWORKS.AVALANCHE),
  sanitizeInput,
  async (req, res) => {
    try {
      const { tokenIn, tokenOut, amountIn, slippage = 1.0 } = req.body;
      
      // Verifica se a wallet privada está configurada
      if (!process.env.WALLET_PRIVATE_KEY) {
        return res.status(500).json({
          error: 'Wallet privada não configurada'
        });
      }

      const provider = new ethers.JsonRpcProvider(NETWORKS.AVALANCHE.rpcUrl);
      const wallet = new ethers.Wallet(process.env.WALLET_PRIVATE_KEY, provider);
      const traderJoeService = new TraderJoeService(provider, wallet);

      // Obtém o preço para calcular amountOutMin
      const price = await traderJoeService.getPrice(tokenIn, tokenOut, amountIn);
      const amountOutMin = traderJoeService.calculateSlippage(price.amountOut, slippage);

      // Executa o swap
      let swapResult;
      if (tokenIn === TRADER_JOE.WAVAX) {
        // Swap de AVAX para token
        swapResult = await traderJoeService.swapAVAXForTokens(tokenOut, amountOutMin, slippage, signedTransaction);
      } else if (tokenOut === TRADER_JOE.WAVAX) {
        // Swap de token para AVAX
        swapResult = await traderJoeService.swapTokensForAVAX(tokenIn, amountIn, amountOutMin, slippage, signedTransaction);
      } else {
        // Swap de token para token
        swapResult = await traderJoeService.swapTokensForTokens(tokenIn, tokenOut, amountIn, amountOutMin, slippage, signedTransaction);
      }

      res.json({
        success: true,
        protocol: 'Trader Joe',
        network: NETWORKS.AVALANCHE.name,
        swap: swapResult
      });
    } catch (error) {
      console.error('Erro ao executar swap Trader Joe:', error);
      res.status(500).json({
        error: 'Erro ao executar swap',
        details: error.message
      });
    }
  }
);



/**
 * @route POST /swap/execute/best
 * @desc Executa swap no protocolo com melhor preço
 * @access Private (com wallet privada)
 */
router.post('/execute/best', 
  verifySignature, 
  validateSwapParams,
  swapRateLimiter,
  validateNetwork(NETWORKS.AVALANCHE),
  sanitizeInput,
  async (req, res) => {
    try {
      const { tokenIn, tokenOut, amountIn, slippage = 1.0 } = req.body;
      
      // Verifica se a wallet privada está configurada
      if (!process.env.WALLET_PRIVATE_KEY) {
        return res.status(500).json({
          error: 'Wallet privada não configurada'
        });
      }

      const provider = new ethers.JsonRpcProvider(NETWORKS.AVALANCHE.rpcUrl);
      const wallet = new ethers.Wallet(process.env.WALLET_PRIVATE_KEY, provider);
      const traderJoeService = new TraderJoeService(provider, wallet);

      // Obtém o preço para calcular amountOutMin
      const price = await traderJoeService.getPrice(tokenIn, tokenOut, amountIn);
      const amountOutMin = traderJoeService.calculateSlippage(price.amountOut, slippage);

      // Executa o swap no Trader Joe
      let swapResult;
      if (tokenIn === TRADER_JOE.WAVAX) {
        // Swap de AVAX para token
        swapResult = await traderJoeService.swapAVAXForTokens(tokenOut, amountOutMin, slippage, signedTransaction);
      } else if (tokenOut === TRADER_JOE.WAVAX) {
        // Swap de token para AVAX
        swapResult = await traderJoeService.swapTokensForAVAX(tokenIn, amountIn, amountOutMin, slippage, signedTransaction);
      } else {
        // Swap de token para token
        swapResult = await traderJoeService.swapTokensForTokens(tokenIn, tokenOut, amountIn, amountOutMin, slippage, signedTransaction);
      }

      res.json({
        success: true,
        protocol: 'Trader Joe',
        network: NETWORKS.AVALANCHE.name,
        note: 'Trader Joe é o único protocolo de swap suportado atualmente',
        swap: swapResult
      });
    } catch (error) {
      console.error('Erro ao executar swap no melhor protocolo:', error);
      res.status(500).json({
        error: 'Erro ao executar swap',
        details: error.message
      });
    }
  }
);

/**
 * @route GET /swap/tokens/common
 * @desc Lista tokens comuns disponíveis para swap
 * @access Public
 */
router.get('/tokens/common', async (req, res) => {
  try {
    const priceService = new PriceService();
    const prices = await priceService.getAvalancheCommonTokenPrices();
    
    res.json({
      success: true,
      network: NETWORKS.AVALANCHE.name,
      tokens: Object.entries(COMMON_TOKENS).map(([symbol, address]) => ({
        symbol,
        address,
        price: prices[symbol]?.price || null,
        priceChange24h: prices[symbol]?.priceChange24h || null
      }))
    });
  } catch (error) {
    console.error('Erro ao obter tokens comuns:', error);
    res.status(500).json({
      error: 'Erro ao obter tokens comuns',
      details: error.message
    });
  }
});

/**
 * @route GET /swap/slippage/options
 * @desc Lista opções de slippage disponíveis
 * @access Public
 */
router.get('/slippage/options', (req, res) => {
  res.json({
    success: true,
    options: SLIPPAGE_OPTIONS,
    description: 'Percentuais de slippage disponíveis para swaps'
  });
});

/**
 * @route POST /swap/quote
 * @desc Obtém cotação detalhada para um swap
 * @access Public (com assinatura)
 */
router.post('/quote', 
  verifySignature, 
  swapRateLimiter,
  async (req, res) => {
    try {
      const { tokenIn, tokenOut, amountIn, slippage = 1.0 } = req.body;
      
      if (!tokenIn || !tokenOut || !amountIn) {
        return res.status(400).json({
          error: 'tokenIn, tokenOut e amountIn são obrigatórios'
        });
      }

      const provider = new ethers.JsonRpcProvider(NETWORKS.AVALANCHE.rpcUrl);
      const traderJoeService = new TraderJoeService(provider);
      const priceService = new PriceService();

      // Obtém preço do Trader Joe
      const price = await traderJoeService.getPrice(tokenIn, tokenOut, amountIn);

      // Obtém informações dos tokens
      const [tokenInInfo, tokenOutInfo] = await Promise.all([
        traderJoeService.getTokenInfo(tokenIn),
        traderJoeService.getTokenInfo(tokenOut)
      ]);

      // Calcula slippage para o Trader Joe
      const amountOutMin = traderJoeService.calculateSlippage(price.amountOut, slippage);

      // Obtém preços de mercado via CoinGecko
      let marketPrices = {};
      try {
        marketPrices = await priceService.getAvalancheCommonTokenPrices();
      } catch (error) {
        console.warn('Não foi possível obter preços de mercado:', error.message);
      }

      const quote = {
        success: true,
        network: NETWORKS.AVALANCHE.name,
        protocol: 'Trader Joe',
        tokens: {
          input: tokenInInfo,
          output: tokenOutInfo
        },
        amountIn: amountIn.toString(),
        slippage: `${slippage}%`,
        amountOut: price.amountOut,
        amountOutMin: amountOutMin.toString(),
        priceImpact: calculatePriceImpact(amountIn, price.amountOut, marketPrices),
        estimatedGas: '500000', // Estimativa padrão
        note: 'Trader Joe é o único protocolo de swap suportado atualmente',
        timestamp: Date.now()
      };

      res.json(quote);
    } catch (error) {
      console.error('Erro ao obter cotação:', error);
      res.status(500).json({
        error: 'Erro ao obter cotação',
        details: error.message
      });
    }
  }
);

/**
 * Função auxiliar para calcular impacto no preço
 */
function calculatePriceImpact(amountIn, amountOut, marketPrices) {
  try {
    // Implementação simplificada - em produção, você calcularia baseado nas reservas de liquidez
    return '0.1%'; // Placeholder
  } catch (error) {
    return 'N/A';
  }
}

module.exports = router;
