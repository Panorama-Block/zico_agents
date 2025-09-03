const { ethers } = require('ethers');

// Configurações para teste
const API_BASE_URL = 'http://localhost:3001';
const WALLET_ADDRESS = '0x6B509c04e3caA2207b8f2A60A067a8ddED03b8d0'; // Endereço da sua wallet
const RPC_URL = 'https://api.avax.network/ext/bc/C/rpc';

// Endereços de tokens comuns na Avalanche
const TOKENS = {
  WAVAX: '0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7',
  USDC: '0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E',
  USDT: '0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7',
  JOE: '0x6e84a6216eA6dACC71eE8E6b0a5B7322EEbC0fDd'
};

class APITester {
  constructor() {
    this.walletAddress = WALLET_ADDRESS;
    this.provider = new ethers.JsonRpcProvider(RPC_URL);
  }

  /**
   * Cria uma requisição autenticada
   */
  createAuthenticatedRequest(data = {}) {
    const timestamp = Date.now();
    const message = `timestamp:${timestamp}`;
    
    return {
      address: this.walletAddress,
      signature: '', // Será preenchido após assinatura
      message: message,
      timestamp: timestamp,
      ...data
    };
  }

  /**
   * Simula assinatura de uma requisição (em produção, isso viria do frontend)
   */
  async signRequest(requestBody) {
    const message = requestBody.message;
    // Em produção, a assinatura viria do smart wallet do frontend
    // Aqui simulamos apenas para teste
    const signature = '0x' + '1'.repeat(130); // Assinatura simulada
    return { ...requestBody, signature };
  }

  /**
   * Faz uma requisição HTTP
   */
  async makeRequest(endpoint, method = 'GET', body = null) {
    const url = `${API_BASE_URL}${endpoint}`;
    const options = {
      method,
      headers: {
        'Content-Type': 'application/json'
      }
    };

    if (body) {
      options.body = JSON.stringify(body);
    }

    try {
      const response = await fetch(url, options);
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${data.error || 'Erro desconhecido'}`);
      }
      
      return data;
    } catch (error) {
      console.error(`❌ Erro na requisição para ${endpoint}:`, error.message);
      throw error;
    }
  }

  /**
   * Testa endpoints básicos da API
   */
  async testBasicEndpoints() {
    console.log('🧪 Testando endpoints básicos...\n');

    try {
      // Health check
      const health = await this.makeRequest('/health');
      console.log('✅ Health Check:', health.status);

      // API Info
      const info = await this.makeRequest('/info');
      console.log('✅ API Info:', info.name, 'v' + info.version);

      // Network Status
      const networkStatus = await this.makeRequest('/network/status');
      console.log('✅ Network Status:', networkStatus.network.name);

      // Configuration
      const config = await this.makeRequest('/config');
      console.log('✅ Configuration:', config.network.chainId);

    } catch (error) {
      console.error('❌ Erro nos endpoints básicos:', error.message);
    }
  }

  /**
   * Testa endpoints de preços
   */
  async testPriceEndpoints() {
    console.log('\n💰 Testando endpoints de preços...\n');

    try {
      // Preços comuns da Avalanche
      const commonPrices = await this.makeRequest('/price/avalanche/common');
      console.log('✅ Preços comuns:', Object.keys(commonPrices.data).length, 'tokens');

      // Preço do Bitcoin
      const bitcoinPrice = await this.makeRequest('/price/coingecko/bitcoin');
      console.log('✅ Preço Bitcoin:', `$${bitcoinPrice.data.price}`);

      // Tendências de mercado
      const trends = await this.makeRequest('/price/trending');
      console.log('✅ Tendências:', trends.data.trendingCoins.length, 'tokens');

      // Estatísticas globais
      const globalStats = await this.makeRequest('/price/global');
      console.log('✅ Estatísticas globais:', `$${globalStats.data.totalMarketCap.usd}`);

    } catch (error) {
      console.error('❌ Erro nos endpoints de preços:', error.message);
    }
  }

  /**
   * Testa endpoints de swap (requer autenticação)
   */
  async testSwapEndpoints() {
    console.log('\n🔄 Testando endpoints de swap...\n');

    try {
      // Lista tokens comuns
      const commonTokens = await this.makeRequest('/swap/tokens/common');
      console.log('✅ Tokens comuns:', commonTokens.tokens.length, 'tokens');

      // Opções de slippage
      const slippageOptions = await this.makeRequest('/swap/slippage/options');
      console.log('✅ Opções de slippage:', Object.keys(slippageOptions.options).length, 'opções');

      // Testa cotação (requer autenticação)
      const quoteRequest = this.createAuthenticatedRequest({
        tokenIn: TOKENS.WAVAX,
        tokenOut: TOKENS.USDC,
        amountIn: '1000000000000000000', // 1 AVAX
        slippage: 1.0
      });

      const signedQuoteRequest = await this.signRequest(quoteRequest);
      const quote = await this.makeRequest('/swap/quote', 'POST', signedQuoteRequest);
      console.log('✅ Cotação obtida para Trader Joe');

    } catch (error) {
      console.error('❌ Erro nos endpoints de swap:', error.message);
    }
  }

  /**
   * Testa comparação de preços
   */
  async testPriceComparison() {
    console.log('\n🏆 Testando comparação de preços...\n');

    try {
      const compareRequest = this.createAuthenticatedRequest({
        tokenIn: TOKENS.WAVAX,
        tokenOut: TOKENS.USDC,
        amountIn: '1000000000000000000' // 1 AVAX
      });

      const signedCompareRequest = await this.signRequest(compareRequest);
      const comparison = await this.makeRequest('/swap/price/compare', 'POST', signedCompareRequest);
      
      console.log('✅ Preço obtido:');
      console.log(`   Protocolo: ${comparison.protocol}`);
      console.log(`   Amount Out: ${comparison.data.amountOut}`);
      console.log(`   Note: ${comparison.note}`);

    } catch (error) {
      console.error('❌ Erro na comparação de preços:', error.message);
    }
  }

  /**
   * Testa informações de tokens
   */
  async testTokenInfo() {
    console.log('\n🪙 Testando informações de tokens...\n');

    try {
      // Informações do AVAX
      const avaxInfo = await this.makeRequest(`/price/token/avalanche-2`);
      console.log('✅ Informações AVAX:', avaxInfo.data.symbol, '-', avaxInfo.data.name);

      // Histórico de preços do Bitcoin
      const btcHistory = await this.makeRequest('/price/history/bitcoin?days=1');
      console.log('✅ Histórico Bitcoin:', btcHistory.data.prices.length, 'pontos de dados');

    } catch (error) {
      console.error('❌ Erro nas informações de tokens:', error.message);
    }
  }

  /**
   * Executa todos os testes
   */
  async runAllTests() {
    console.log('🚀 Iniciando testes da Zico Swap API\n');
    console.log(`📍 API: ${API_BASE_URL}`);
    console.log(`🔗 Rede: Avalanche C-Chain`);
    console.log(`👛 Wallet: ${this.walletAddress}\n`);

    try {
      await this.testBasicEndpoints();
      await this.testPriceEndpoints();
      await this.testSwapEndpoints();
      await this.testPriceComparison();
      await this.testTokenInfo();

      console.log('\n🎉 Todos os testes foram executados!');
      console.log('\n💡 Para executar swaps reais, use os endpoints de execução com transações assinadas pelo frontend.');

    } catch (error) {
      console.error('\n💥 Erro durante os testes:', error.message);
    }
  }
}

// Função principal
async function main() {
  // Verifica se o fetch está disponível (Node.js 18+)
  if (typeof fetch === 'undefined') {
    console.log('📦 Instalando node-fetch...');
    const { default: fetch } = await import('node-fetch');
    global.fetch = fetch;
  }

  const tester = new APITester();
  await tester.runAllTests();
}

// Executa os testes se o arquivo for executado diretamente
if (require.main === module) {
  main().catch(console.error);
}

module.exports = APITester;
