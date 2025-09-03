const { ethers } = require('ethers');
const axios = require('axios');
const { TRADER_JOE, COMMON_TOKENS, API_URLS } = require('../config/constants');

// ABI simplificado para Trader Joe Router
const TRADER_JOE_ROUTER_ABI = [
  'function getAmountsOut(uint amountIn, address[] memory path) public view returns (uint[] memory amounts)',
  'function swapExactTokensForTokens(uint amountIn, uint amountOutMin, address[] calldata path, address to, uint deadline) external returns (uint[] memory amounts)',
  'function swapExactAVAXForTokens(uint amountOutMin, address[] calldata path, address to, uint deadline) external payable returns (uint[] memory amounts)',
  'function swapExactTokensForAVAX(uint amountIn, uint amountOutMin, address[] calldata path, address to, uint deadline) external returns (uint[] memory amounts)',
  'function swapExactTokensForTokensSupportingFeeOnTransferTokens(uint amountIn, uint amountOutMin, address[] calldata path, address to, uint deadline) external',
  'function swapExactAVAXForTokensSupportingFeeOnTransferTokens(uint amountOutMin, address[] calldata path, address to, uint deadline) external payable returns (uint[] memory amounts)',
  'function swapExactTokensForAVAXSupportingFeeOnTransferTokens(uint amountIn, uint amountOutMin, address[] calldata path, address to, uint deadline) external',
  'function getAmountOut(uint amountIn, uint reserveIn, uint reserveOut) public pure returns (uint amountOut)',
  'function getAmountIn(uint amountOut, uint reserveIn, uint reserveOut) public pure returns (uint amountIn)'
];

// ABI para ERC20
const ERC20_ABI = [
  'function name() view returns (string)',
  'function symbol() view returns (string)',
  'function decimals() view returns (uint8)',
  'function totalSupply() view returns (uint256)',
  'function balanceOf(address) view returns (uint256)',
  'function transfer(address to, uint256 amount) returns (bool)',
  'function allowance(address owner, address spender) view returns (uint256)',
  'function approve(address spender, uint256 amount) returns (bool)',
  'function transferFrom(address from, address to, uint256 amount) returns (bool)'
];

class TraderJoeService {
  constructor(provider, walletAddress = null) {
    this.provider = provider;
    this.walletAddress = walletAddress;
    // Para operações de leitura, não precisamos de wallet
    this.router = new ethers.Contract(TRADER_JOE.ROUTER, TRADER_JOE_ROUTER_ABI, provider);
  }

  /**
   * Obtém o preço de um token em relação a outro
   */
  async getPrice(tokenIn, tokenOut, amountIn = '1000000000000000000') { // 1 token por padrão
    try {
      const path = [tokenIn, tokenOut];
      const amounts = await this.router.getAmountsOut(amountIn, path);
      return {
        tokenIn,
        tokenOut,
        amountIn: amounts[0].toString(),
        amountOut: amounts[1].toString(),
        price: amounts[1].toString()
      };
    } catch (error) {
      throw new Error(`Erro ao obter preço: ${error.message}`);
    }
  }

  /**
   * Obtém preços de múltiplos pares
   */
  async getMultiplePrices(pairs) {
    try {
      const prices = {};
      for (const pair of pairs) {
        const { tokenIn, tokenOut, amountIn } = pair;
        const price = await this.getPrice(tokenIn, tokenOut, amountIn);
        prices[`${tokenIn}-${tokenOut}`] = price;
      }
      return prices;
    } catch (error) {
      throw new Error(`Erro ao obter múltiplos preços: ${error.message}`);
    }
  }

  /**
   * Calcula o slippage para uma transação
   */
  calculateSlippage(amountOut, slippagePercent) {
    const slippageMultiplier = slippagePercent / 100;
    const minAmountOut = amountOut * (1 - slippageMultiplier);
    return ethers.parseUnits(minAmountOut.toString(), 18);
  }

  /**
   * Executa swap de tokens para tokens
   * @param {string} tokenIn - Endereço do token de entrada
   * @param {string} tokenOut - Endereço do token de saída
   * @param {string} amountIn - Quantidade de entrada
   * @param {string} amountOutMin - Quantidade mínima de saída
   * @param {number} slippage - Percentual de slippage
   * @param {string} signedTransaction - Transação assinada pelo frontend
   * @returns {Object} Resultado da transação
   */
  async swapTokensForTokens(tokenIn, tokenOut, amountIn, amountOutMin, slippage = 1.0, signedTransaction = null) {
    try {
      if (!signedTransaction) {
        throw new Error('Transação assinada é obrigatória para executar swaps');
      }

      // Envia a transação assinada
      const tx = await this.provider.broadcastTransaction(signedTransaction);
      
      return {
        txHash: tx.hash,
        status: 'pending',
        details: {
          tokenIn,
          tokenOut,
          amountIn: amountIn.toString(),
          amountOutMin: amountOutMin.toString(),
          slippage: `${slippage}%`,
          note: 'Transação enviada via smart wallet do frontend'
        }
      };
    } catch (error) {
      throw new Error(`Erro no swap de tokens: ${error.message}`);
    }
  }

  /**
   * Executa swap de AVAX para tokens
   * @param {string} tokenOut - Endereço do token de saída
   * @param {string} amountOutMin - Quantidade mínima de saída
   * @param {number} slippage - Percentual de slippage
   * @param {string} signedTransaction - Transação assinada pelo frontend
   * @returns {Object} Resultado da transação
   */
  async swapAVAXForTokens(tokenOut, amountOutMin, slippage = 1.0, signedTransaction = null) {
    try {
      if (!signedTransaction) {
        throw new Error('Transação assinada é obrigatória para executar swaps');
      }

      // Envia a transação assinada
      const tx = await this.provider.broadcastTransaction(signedTransaction);
      
      return {
        txHash: tx.hash,
        status: 'pending',
        details: {
          tokenIn: 'AVAX',
          tokenOut,
          amountOutMin: amountOutMin.toString(),
          slippage: `${slippage}%`,
          note: 'Transação enviada via smart wallet do frontend'
        }
      };
    } catch (error) {
      throw new Error(`Erro no swap de AVAX para tokens: ${error.message}`);
    }
  }

  /**
   * Executa swap de tokens para AVAX
   * @param {string} tokenIn - Endereço do token de entrada
   * @param {string} amountIn - Quantidade de entrada
   * @param {string} amountOutMin - Quantidade mínima de saída
   * @param {number} slippage - Percentual de slippage
   * @param {string} signedTransaction - Transação assinada pelo frontend
   * @returns {Object} Resultado da transação
   */
  async swapTokensForAVAX(tokenIn, amountIn, amountOutMin, slippage = 1.0, signedTransaction = null) {
    try {
      if (!signedTransaction) {
        throw new Error('Transação assinada é obrigatória para executar swaps');
      }

      // Envia a transação assinada
      const tx = await this.provider.broadcastTransaction(signedTransaction);
      
      return {
        txHash: tx.hash,
        status: 'pending',
        details: {
          tokenIn,
          tokenOut: 'AVAX',
          amountIn: amountIn.toString(),
          amountOutMin: amountOutMin.toString(),
          slippage: `${slippage}%`,
          note: 'Transação enviada via smart wallet do frontend'
        }
      };
    } catch (error) {
      throw new Error(`Erro no swap de tokens para AVAX: ${error.message}`);
    }
  }

  /**
   * Obtém informações de liquidez de um par
   */
  async getLiquidityInfo(tokenA, tokenB) {
    try {
      const response = await axios.get(`${API_URLS.TRADER_JOE}/v1/pairs/${tokenA}/${tokenB}`);
      return response.data;
    } catch (error) {
      throw new Error(`Erro ao obter informações de liquidez: ${error.message}`);
    }
  }

  /**
   * Obtém histórico de preços de um token
   */
  async getPriceHistory(tokenAddress, days = 7) {
    try {
      const response = await axios.get(`${API_URLS.TRADER_JOE}/v1/tokens/${tokenAddress}/price-history?days=${days}`);
      return response.data;
    } catch (error) {
      throw new Error(`Erro ao obter histórico de preços: ${error.message}`);
    }
  }

  /**
   * Obtém estatísticas de volume de um par
   */
  async getVolumeStats(tokenA, tokenB, period = '24h') {
    try {
      const response = await axios.get(`${API_URLS.TRADER_JOE}/v1/pairs/${tokenA}/${tokenB}/volume?period=${period}`);
      return response.data;
    } catch (error) {
      throw new Error(`Erro ao obter estatísticas de volume: ${error.message}`);
    }
  }

  /**
   * Verifica se um token tem suporte a fee on transfer
   */
  async supportsFeeOnTransfer(tokenAddress) {
    try {
      const tokenContract = new ethers.Contract(tokenAddress, ERC20_ABI, this.provider);
      // Tenta chamar a função que suporta fee on transfer
      await this.router.swapExactTokensForTokensSupportingFeeOnTransferTokens(
        ethers.parseUnits('1', 18),
        0,
        [tokenAddress, TRADER_JOE.WAVAX],
        this.walletAddress || '0x0000000000000000000000000000000000000000',
        Math.floor(Date.now() / 1000) + 1200
      );
      return true;
    } catch (error) {
      return false;
    }
  }

  /**
   * Obtém informações de um token
   */
  async getTokenInfo(tokenAddress) {
    try {
      const tokenContract = new ethers.Contract(tokenAddress, ERC20_ABI, this.provider);
      const [name, symbol, decimals, totalSupply] = await Promise.all([
        tokenContract.name(),
        tokenContract.symbol(),
        tokenContract.decimals(),
        tokenContract.totalSupply()
      ]);

      return {
        address: tokenAddress,
        name,
        symbol,
        decimals: decimals.toString(),
        totalSupply: totalSupply.toString(),
        formattedTotalSupply: ethers.formatUnits(totalSupply, decimals)
      };
    } catch (error) {
      throw new Error(`Erro ao obter informações do token: ${error.message}`);
    }
  }

  /**
   * Obtém o balance de um token para uma wallet
   */
  async getTokenBalance(tokenAddress, walletAddress) {
    try {
      const tokenContract = new ethers.Contract(tokenAddress, ERC20_ABI, this.provider);
      const balance = await tokenContract.balanceOf(walletAddress);
      const decimals = await tokenContract.decimals();
      
      return {
        tokenAddress,
        walletAddress,
        balance: balance.toString(),
        formattedBalance: ethers.formatUnits(balance, decimals)
      };
    } catch (error) {
      throw new Error(`Erro ao obter balance do token: ${error.message}`);
    }
  }
}

module.exports = TraderJoeService;
