const express = require('express');
const PriceService = require('../services/priceService');
const { verifySignature, createRateLimiter, requestLogger } = require('../middleware/auth');
const { NETWORKS } = require('../config/constants');

const router = express.Router();

// Rate limiting para rotas de preço
const priceRateLimiter = createRateLimiter(100, 5 * 60 * 1000); // 100 requests por 5 minutos

/**
 * @route GET /price/avalanche/common
 * @desc Obtém preços dos tokens comuns da Avalanche
 * @access Public
 */
router.get('/avalanche/common', 
  priceRateLimiter,
  requestLogger,
  async (req, res) => {
    try {
      const { vs_currency = 'usd' } = req.query;
      const priceService = new PriceService();
      
      const prices = await priceService.getAvalancheCommonTokenPrices(vs_currency);
      
      res.json({
        success: true,
        network: NETWORKS.AVALANCHE.name,
        vsCurrency: vs_currency,
        timestamp: Date.now(),
        data: prices
      });
    } catch (error) {
      console.error('Erro ao obter preços comuns da Avalanche:', error);
      res.status(500).json({
        error: 'Erro ao obter preços',
        details: error.message
      });
    }
  }
);

/**
 * @route GET /price/coingecko/:tokenId
 * @desc Obtém preço de um token específico via CoinGecko
 * @access Public
 */
router.get('/coingecko/:tokenId', 
  priceRateLimiter,
  requestLogger,
  async (req, res) => {
    try {
      const { tokenId } = req.params;
      const { vs_currency = 'usd' } = req.query;
      
      const priceService = new PriceService();
      const price = await priceService.getCoinGeckoPrice(tokenId, vs_currency);
      
      res.json({
        success: true,
        source: 'coingecko',
        data: price
      });
    } catch (error) {
      console.error('Erro ao obter preço CoinGecko:', error);
      res.status(500).json({
        error: 'Erro ao obter preço',
        details: error.message
      });
    }
  }
);

/**
 * @route GET /price/avalanche/token/:contractAddress
 * @desc Obtém preço de um token específico da rede Avalanche
 * @access Public
 */
router.get('/avalanche/token/:contractAddress', 
  priceRateLimiter,
  requestLogger,
  async (req, res) => {
    try {
      const { contractAddress } = req.params;
      const { vs_currency = 'usd' } = req.query;
      
      const priceService = new PriceService();
      const price = await priceService.getAvalancheTokenPrice(contractAddress, vs_currency);
      
      res.json({
        success: true,
        network: NETWORKS.AVALANCHE.name,
        data: price
      });
    } catch (error) {
      console.error('Erro ao obter preço do token Avalanche:', error);
      res.status(500).json({
        error: 'Erro ao obter preço do token',
        details: error.message
      });
    }
  }
);

/**
 * @route GET /price/history/:tokenId
 * @desc Obtém histórico de preços de um token
 * @access Public
 */
router.get('/history/:tokenId', 
  priceRateLimiter,
  requestLogger,
  async (req, res) => {
    try {
      const { tokenId } = req.params;
      const { vs_currency = 'usd', days = '7' } = req.query;
      
      const priceService = new PriceService();
      const history = await priceService.getPriceHistory(tokenId, vs_currency, parseInt(days));
      
      res.json({
        success: true,
        source: 'coingecko',
        data: history
      });
    } catch (error) {
      console.error('Erro ao obter histórico de preços:', error);
      res.status(500).json({
        error: 'Erro ao obter histórico de preços',
        details: error.message
      });
    }
  }
);

/**
 * @route GET /price/token/:tokenId
 * @desc Obtém informações detalhadas de um token
 * @access Public
 */
router.get('/token/:tokenId', 
  priceRateLimiter,
  requestLogger,
  async (req, res) => {
    try {
      const { tokenId } = req.params;
      
      const priceService = new PriceService();
      const tokenInfo = await priceService.getTokenInfo(tokenId);
      
      res.json({
        success: true,
        source: 'coingecko',
        data: tokenInfo
      });
    } catch (error) {
      console.error('Erro ao obter informações do token:', error);
      res.status(500).json({
        error: 'Erro ao obter informações do token',
        details: error.message
      });
    }
  }
);

/**
 * @route GET /price/trending
 * @desc Obtém tendências de mercado
 * @access Public
 */
router.get('/trending', 
  priceRateLimiter,
  requestLogger,
  async (req, res) => {
    try {
      const { vs_currency = 'usd' } = req.query;
      
      const priceService = new PriceService();
      const trends = await priceService.getMarketTrends(vs_currency);
      
      res.json({
        success: true,
        source: 'coingecko',
        data: trends
      });
    } catch (error) {
      console.error('Erro ao obter tendências de mercado:', error);
      res.status(500).json({
        error: 'Erro ao obter tendências de mercado',
        details: error.message
      });
    }
  }
);

/**
 * @route GET /price/global
 * @desc Obtém estatísticas globais do mercado
 * @access Public
 */
router.get('/global', 
  priceRateLimiter,
  requestLogger,
  async (req, res) => {
    try {
      const { vs_currency = 'usd' } = req.query;
      
      const priceService = new PriceService();
      const globalStats = await priceService.getGlobalMarketStats(vs_currency);
      
      res.json({
        success: true,
        source: 'coingecko',
        data: globalStats
      });
    } catch (error) {
      console.error('Erro ao obter estatísticas globais:', error);
      res.status(500).json({
        error: 'Erro ao obter estatísticas globais',
        details: error.message
      });
    }
  }
);

/**
 * @route POST /price/batch
 * @desc Obtém preços de múltiplos tokens de uma vez
 * @access Public (com assinatura para rate limit personalizado)
 */
router.post('/batch', 
  verifySignature,
  priceRateLimiter,
  requestLogger,
  async (req, res) => {
    try {
      const { tokenIds, vs_currency = 'usd' } = req.body;
      
      if (!tokenIds || !Array.isArray(tokenIds) || tokenIds.length === 0) {
        return res.status(400).json({
          error: 'tokenIds deve ser um array não vazio'
        });
      }

      if (tokenIds.length > 100) {
        return res.status(400).json({
          error: 'Máximo de 100 tokens por requisição'
        });
      }
      
      const priceService = new PriceService();
      const prices = await priceService.getMultipleCoinGeckoPrices(tokenIds, vs_currency);
      
      res.json({
        success: true,
        source: 'coingecko',
        vsCurrency: vs_currency,
        count: Object.keys(prices).length,
        timestamp: Date.now(),
        data: prices
      });
    } catch (error) {
      console.error('Erro ao obter preços em lote:', error);
      res.status(500).json({
        error: 'Erro ao obter preços em lote',
        details: error.message
      });
    }
  }
);

/**
 * @route GET /price/cache/stats
 * @desc Obtém estatísticas do cache de preços
 * @access Public
 */
router.get('/cache/stats', 
  requestLogger,
  async (req, res) => {
    try {
      const priceService = new PriceService();
      const cacheStats = priceService.getCacheStats();
      
      res.json({
        success: true,
        data: cacheStats
      });
    } catch (error) {
      console.error('Erro ao obter estatísticas do cache:', error);
      res.status(500).json({
        error: 'Erro ao obter estatísticas do cache',
        details: error.message
      });
    }
  }
);

/**
 * @route POST /price/cache/clear
 * @desc Limpa o cache de preços
 * @access Public (com assinatura)
 */
router.post('/cache/clear', 
  verifySignature,
  requestLogger,
  async (req, res) => {
    try {
      const priceService = new PriceService();
      priceService.clearExpiredCache();
      
      res.json({
        success: true,
        message: 'Cache limpo com sucesso',
        timestamp: Date.now()
      });
    } catch (error) {
      console.error('Erro ao limpar cache:', error);
      res.status(500).json({
        error: 'Erro ao limpar cache',
        details: error.message
      });
    }
  }
);

/**
 * @route GET /price/status
 * @desc Verifica o status dos serviços de preço
 * @access Public
 */
router.get('/status', 
  requestLogger,
  async (req, res) => {
    try {
      const priceService = new PriceService();
      
      // Testa conexão com CoinGecko
      let coingeckoStatus = 'unknown';
      try {
        await priceService.getCoinGeckoPrice('bitcoin', 'usd');
        coingeckoStatus = 'healthy';
      } catch (error) {
        coingeckoStatus = 'unhealthy';
      }

      const status = {
        timestamp: Date.now(),
        services: {
          coingecko: coingeckoStatus,
          cache: 'healthy'
        },
        network: NETWORKS.AVALANCHE.name,
        uptime: process.uptime()
      };
      
      res.json({
        success: true,
        data: status
      });
    } catch (error) {
      console.error('Erro ao verificar status:', error);
      res.status(500).json({
        error: 'Erro ao verificar status',
        details: error.message
      });
    }
  }
);

module.exports = router;
