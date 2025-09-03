const axios = require('axios');
const { API_URLS, COMMON_TOKENS } = require('../config/constants');

class PriceService {
  constructor() {
    this.coingeckoBaseUrl = API_URLS.COINGECKO;
    this.cache = new Map();
    this.cacheExpiry = 5 * 60 * 1000; // 5 minutos
  }

  /**
   * Obtém preço de um token via CoinGecko
   */
  async getCoinGeckoPrice(tokenId, vsCurrency = 'usd') {
    try {
      const cacheKey = `coingecko_${tokenId}_${vsCurrency}`;
      const cached = this.getCachedPrice(cacheKey);
      if (cached) return cached;

      const response = await axios.get(
        `${this.coingeckoBaseUrl}/simple/price`,
        {
          params: {
            ids: tokenId,
            vs_currencies: vsCurrency,
            include_24hr_change: true,
            include_market_cap: true,
            include_24hr_vol: true
          },
          timeout: 10000
        }
      );

      if (response.data && response.data[tokenId]) {
        const priceData = response.data[tokenId];
        const result = {
          source: 'coingecko',
          tokenId,
          vsCurrency,
          price: priceData[vsCurrency],
          priceChange24h: priceData[`${vsCurrency}_24h_change`],
          marketCap: priceData[`${vsCurrency}_market_cap`],
          volume24h: priceData[`${vsCurrency}_24h_vol`],
          timestamp: Date.now()
        };

        this.setCachedPrice(cacheKey, result);
        return result;
      }

      throw new Error('Dados de preço não encontrados');
    } catch (error) {
      throw new Error(`Erro ao obter preço do CoinGecko: ${error.message}`);
    }
  }

  /**
   * Obtém preços de múltiplos tokens via CoinGecko
   */
  async getMultipleCoinGeckoPrices(tokenIds, vsCurrency = 'usd') {
    try {
      const response = await axios.get(
        `${this.coingeckoBaseUrl}/simple/price`,
        {
          params: {
            ids: tokenIds.join(','),
            vs_currencies: vsCurrency,
            include_24hr_change: true,
            include_market_cap: true,
            include_24hr_vol: true
          },
          timeout: 15000
        }
      );

      const results = {};
      for (const tokenId of tokenIds) {
        if (response.data && response.data[tokenId]) {
          const priceData = response.data[tokenId];
          results[tokenId] = {
            source: 'coingecko',
            tokenId,
            vsCurrency,
            price: priceData[vsCurrency],
            priceChange24h: priceData[`${vsCurrency}_24h_change`],
            marketCap: priceData[`${vsCurrency}_market_cap`],
            volume24h: priceData[`${vsCurrency}_24h_vol`],
            timestamp: Date.now()
          };
        }
      }

      return results;
    } catch (error) {
      throw new Error(`Erro ao obter múltiplos preços do CoinGecko: ${error.message}`);
    }
  }

  /**
   * Obtém preço de um token específico da Avalanche via CoinGecko
   */
  async getAvalancheTokenPrice(contractAddress, vsCurrency = 'usd') {
    try {
      const response = await axios.get(
        `${this.coingeckoBaseUrl}/simple/token_price/avalanche`,
        {
          params: {
            contract_addresses: contractAddress,
            vs_currencies: vsCurrency,
            include_24hr_change: true,
            include_market_cap: true,
            include_24hr_vol: true
          },
          timeout: 10000
        }
      );

      if (response.data && response.data[contractAddress.toLowerCase()]) {
        const priceData = response.data[contractAddress.toLowerCase()];
        return {
          source: 'coingecko_avalanche',
          contractAddress,
          vsCurrency,
          price: priceData[vsCurrency],
          priceChange24h: priceData[`${vsCurrency}_24h_change`],
          marketCap: priceData[`${vsCurrency}_market_cap`],
          volume24h: priceData[`${vsCurrency}_24h_vol`],
          timestamp: Date.now()
        };
      }

      throw new Error('Token não encontrado na rede Avalanche');
    } catch (error) {
      throw new Error(`Erro ao obter preço do token Avalanche: ${error.message}`);
    }
  }

  /**
   * Obtém preços de tokens comuns da Avalanche
   */
  async getAvalancheCommonTokenPrices(vsCurrency = 'usd') {
    try {
      const commonTokenIds = {
        'avalanche-2': 'AVAX',
        'usd-coin': 'USDC',
        'tether': 'USDT',
        'dai': 'DAI',
        'weth': 'WETH',
        'joe': 'JOE',
        'pangolin': 'PNG',
        'chainlink': 'LINK',
        'uniswap': 'UNI'
      };

      const tokenIds = Object.keys(commonTokenIds);
      const prices = await this.getMultipleCoinGeckoPrices(tokenIds, vsCurrency);

      // Adiciona símbolos aos resultados
      const results = {};
      for (const [tokenId, symbol] of Object.entries(commonTokenIds)) {
        if (prices[tokenId]) {
          results[symbol] = {
            ...prices[tokenId],
            symbol
          };
        }
      }

      return results;
    } catch (error) {
      throw new Error(`Erro ao obter preços dos tokens comuns: ${error.message}`);
    }
  }

  /**
   * Obtém histórico de preços de um token
   */
  async getPriceHistory(tokenId, vsCurrency = 'usd', days = 7) {
    try {
      const response = await axios.get(
        `${this.coingeckoBaseUrl}/coins/${tokenId}/market_chart`,
        {
          params: {
            vs_currency: vsCurrency,
            days: days,
            interval: days <= 1 ? 'hourly' : 'daily'
          },
          timeout: 15000
        }
      );

      if (response.data && response.data.prices) {
        return {
          source: 'coingecko',
          tokenId,
          vsCurrency,
          days,
          prices: response.data.prices.map(([timestamp, price]) => ({
            timestamp,
            price,
            date: new Date(timestamp).toISOString()
          })),
          marketCaps: response.data.market_caps || [],
          volumes: response.data.total_volumes || [],
          timestamp: Date.now()
        };
      }

      throw new Error('Histórico de preços não encontrado');
    } catch (error) {
      throw new Error(`Erro ao obter histórico de preços: ${error.message}`);
    }
  }

  /**
   * Obtém informações detalhadas de um token
   */
  async getTokenInfo(tokenId) {
    try {
      const response = await axios.get(
        `${this.coingeckoBaseUrl}/coins/${tokenId}`,
        {
          params: {
            localization: false,
            tickers: false,
            market_data: true,
            community_data: false,
            developer_data: false,
            sparkline: false
          },
          timeout: 15000
        }
      );

      if (response.data) {
        const data = response.data;
        return {
          source: 'coingecko',
          id: data.id,
          name: data.name,
          symbol: data.symbol.toUpperCase(),
          description: data.description?.en || '',
          image: data.image,
          marketData: {
            currentPrice: data.market_data?.current_price || {},
            marketCap: data.market_data?.market_cap || {},
            totalVolume: data.market_data?.total_volume || {},
            priceChange24h: data.market_data?.price_change_percentage_24h || 0,
            priceChange7d: data.market_data?.price_change_percentage_7d || 0,
            priceChange30d: data.market_data?.price_change_percentage_30d || 0,
            ath: data.market_data?.ath || {},
            athChangePercentage: data.market_data?.ath_change_percentage || {},
            atl: data.market_data?.atl || {},
            atlChangePercentage: data.market_data?.atl_change_percentage || {}
          },
          links: data.links || {},
          timestamp: Date.now()
        };
      }

      throw new Error('Informações do token não encontradas');
    } catch (error) {
      throw new Error(`Erro ao obter informações do token: ${error.message}`);
    }
  }

  /**
   * Obtém tendências de mercado
   */
  async getMarketTrends(vsCurrency = 'usd') {
    try {
      const response = await axios.get(
        `${this.coingeckoBaseUrl}/search/trending`,
        {
          timeout: 10000
        }
      );

      if (response.data && response.data.coins) {
        const trendingCoins = response.data.coins.map(coin => ({
          id: coin.item.id,
          name: coin.item.name,
          symbol: coin.item.symbol.toUpperCase(),
          marketCapRank: coin.item.market_cap_rank,
          priceBtc: coin.item.price_btc,
          score: coin.item.score,
          image: coin.item.large
        }));

        return {
          source: 'coingecko',
          vsCurrency,
          trendingCoins,
          timestamp: Date.now()
        };
      }

      throw new Error('Tendências de mercado não encontradas');
    } catch (error) {
      throw new Error(`Erro ao obter tendências de mercado: ${error.message}`);
    }
  }

  /**
   * Obtém estatísticas globais do mercado
   */
  async getGlobalMarketStats(vsCurrency = 'usd') {
    try {
      const response = await axios.get(
        `${this.coingeckoBaseUrl}/global`,
        {
          timeout: 10000
        }
      );

      if (response.data && response.data.data) {
        const data = response.data.data;
        return {
          source: 'coingecko',
          vsCurrency,
          activeCryptocurrencies: data.active_cryptocurrencies,
          totalMarketCap: data.total_market_cap,
          totalVolume: data.total_volume,
          marketCapPercentage: data.market_cap_percentage,
          marketCapChangePercentage24h: data.market_cap_change_percentage_24h_usd,
          timestamp: Date.now()
        };
      }

      throw new Error('Estatísticas globais não encontradas');
    } catch (error) {
      throw new Error(`Erro ao obter estatísticas globais: ${error.message}`);
    }
  }

  /**
   * Gerencia cache de preços
   */
  getCachedPrice(key) {
    const cached = this.cache.get(key);
    if (cached && Date.now() - cached.timestamp < this.cacheExpiry) {
      return cached.data;
    }
    return null;
  }

  setCachedPrice(key, data) {
    this.cache.set(key, {
      data,
      timestamp: Date.now()
    });
  }

  /**
   * Limpa cache expirado
   */
  clearExpiredCache() {
    const now = Date.now();
    for (const [key, value] of this.cache.entries()) {
      if (now - value.timestamp > this.cacheExpiry) {
        this.cache.delete(key);
      }
    }
  }

  /**
   * Obtém estatísticas do cache
   */
  getCacheStats() {
    return {
      size: this.cache.size,
      maxAge: this.cacheExpiry,
      keys: Array.from(this.cache.keys())
    };
  }
}

module.exports = PriceService;
