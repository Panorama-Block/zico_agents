const { ethers } = require('ethers');
const { SECURITY } = require('../config/constants');

/**
 * Middleware para verificar assinatura de wallet
 */
function verifySignature(req, res, next) {
  try {
    const { address, signature, message, timestamp } = req.body;

    // Validação básica dos parâmetros
    if (!address || !signature || !message) {
      return res.status(400).json({
        error: 'Parâmetros inválidos',
        required: ['address', 'signature', 'message'],
        received: { address: !!address, signature: !!signature, message: !!message }
      });
    }

    // Verifica se o timestamp não expirou
    if (timestamp && Date.now() - timestamp > SECURITY.SIGNATURE_EXPIRY) {
      return res.status(401).json({
        error: 'Assinatura expirada',
        message: 'A assinatura deve ser usada dentro de 5 minutos'
      });
    }

    // Verifica se o endereço é válido
    if (!ethers.isAddress(address)) {
      return res.status(400).json({
        error: 'Endereço de wallet inválido',
        address
      });
    }

    // Recupera o endereço da assinatura
    let recoveredAddress;
    try {
      recoveredAddress = ethers.verifyMessage(message, signature);
    } catch (error) {
      return res.status(400).json({
        error: 'Assinatura inválida',
        details: error.message
      });
    }

    // Verifica se o endereço recuperado corresponde ao endereço fornecido
    if (recoveredAddress.toLowerCase() !== address.toLowerCase()) {
      return res.status(401).json({
        error: 'Assinatura não corresponde ao endereço',
        expected: address.toLowerCase(),
        recovered: recoveredAddress.toLowerCase()
      });
    }

    // Adiciona informações verificadas ao request
    req.verifiedAddress = address.toLowerCase();
    req.signatureData = {
      address: address.toLowerCase(),
      message,
      timestamp: timestamp || Date.now()
    };

    next();
  } catch (error) {
    console.error('Erro na verificação de assinatura:', error);
    res.status(500).json({
      error: 'Erro interno na verificação de assinatura',
      details: error.message
    });
  }
}

/**
 * Middleware para verificar se o usuário tem saldo suficiente
 */
function checkBalance(requiredAmount, tokenAddress = null) {
  return async (req, res, next) => {
    try {
      const { address } = req.body;
      
      if (!address) {
        return res.status(400).json({
          error: 'Endereço de wallet é obrigatório'
        });
      }

      // Aqui você pode implementar a lógica para verificar o saldo
      // Por enquanto, apenas passa para o próximo middleware
      req.requiredAmount = requiredAmount;
      req.tokenAddress = tokenAddress;
      
      next();
    } catch (error) {
      console.error('Erro na verificação de saldo:', error);
      res.status(500).json({
        error: 'Erro ao verificar saldo',
        details: error.message
      });
    }
  };
}

/**
 * Middleware para validar parâmetros de swap
 */
function validateSwapParams(req, res, next) {
  try {
    const { tokenIn, tokenOut, amountIn, slippage } = req.body;

    // Validação dos parâmetros obrigatórios
    if (!tokenIn || !tokenOut || !amountIn) {
      return res.status(400).json({
        error: 'Parâmetros obrigatórios ausentes',
        required: ['tokenIn', 'tokenOut', 'amountIn'],
        received: { tokenIn: !!tokenIn, tokenOut: !!tokenOut, amountIn: !!amountIn }
      });
    }

    // Validação dos endereços dos tokens
    if (!ethers.isAddress(tokenIn)) {
      return res.status(400).json({
        error: 'Endereço do token de entrada inválido',
        tokenIn
      });
    }

    if (!ethers.isAddress(tokenOut)) {
      return res.status(400).json({
        error: 'Endereço do token de saída inválido',
        tokenOut
      });
    }

    // Validação do valor de entrada
    if (isNaN(amountIn) || parseFloat(amountIn) <= 0) {
      return res.status(400).json({
        error: 'Valor de entrada deve ser um número positivo',
        amountIn
      });
    }

    // Validação do slippage
    if (slippage !== undefined) {
      if (isNaN(slippage) || slippage < 0 || slippage > 50) {
        return res.status(400).json({
          error: 'Slippage deve estar entre 0 e 50%',
          slippage
        });
      }
    }

    // Validação de valores mínimos e máximos
    const amountInFloat = parseFloat(amountIn);
    if (amountInFloat < parseFloat(SECURITY.MIN_AMOUNT)) {
      return res.status(400).json({
        error: `Valor mínimo não atingido: ${SECURITY.MIN_AMOUNT}`,
        amountIn,
        minimum: SECURITY.MIN_AMOUNT
      });
    }

    if (amountInFloat > parseFloat(SECURITY.MAX_AMOUNT)) {
      return res.status(400).json({
        error: `Valor máximo excedido: ${SECURITY.MAX_AMOUNT}`,
        amountIn,
        maximum: SECURITY.MAX_AMOUNT
      });
    }

    next();
  } catch (error) {
    console.error('Erro na validação dos parâmetros de swap:', error);
    res.status(500).json({
      error: 'Erro interno na validação',
      details: error.message
    });
  }
}

/**
 * Middleware para rate limiting personalizado
 */
function createRateLimiter(maxRequests, windowMs) {
  const requests = new Map();

  return (req, res, next) => {
    const clientId = req.verifiedAddress || req.ip;
    const now = Date.now();
    const windowStart = now - windowMs;

    // Limpa requisições antigas
    if (requests.has(clientId)) {
      requests.set(clientId, requests.get(clientId).filter(timestamp => timestamp > windowStart));
    } else {
      requests.set(clientId, []);
    }

    const clientRequests = requests.get(clientId);

    if (clientRequests.length >= maxRequests) {
      return res.status(429).json({
        error: 'Rate limit excedido',
        message: `Máximo de ${maxRequests} requisições por ${windowMs / 1000} segundos`,
        retryAfter: Math.ceil(windowMs / 1000)
      });
    }

    // Adiciona timestamp da requisição atual
    clientRequests.push(now);
    next();
  };
}

/**
 * Middleware para logging de requisições
 */
function requestLogger(req, res, next) {
  const start = Date.now();
  
  // Log da requisição
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.path} - ${req.ip}`);
  
  // Log da resposta
  res.on('finish', () => {
    const duration = Date.now() - start;
    console.log(`[${new Date().toISOString()}] ${req.method} ${req.path} - ${res.statusCode} - ${duration}ms`);
  });

  next();
}

/**
 * Middleware para validação de rede
 */
function validateNetwork(network) {
  return (req, res, next) => {
    const { chainId } = req.body;
    
    if (chainId && chainId !== network.chainId) {
      return res.status(400).json({
        error: 'Rede incorreta',
        expected: network.chainId,
        received: chainId,
        networkName: network.name
      });
    }

    next();
  };
}

/**
 * Middleware para sanitização de dados
 */
function sanitizeInput(req, res, next) {
  // Sanitiza endereços de wallet
  if (req.body.address) {
    req.body.address = req.body.address.toLowerCase();
  }

  // Sanitiza endereços de tokens
  if (req.body.tokenIn) {
    req.body.tokenIn = req.body.tokenIn.toLowerCase();
  }

  if (req.body.tokenOut) {
    req.body.tokenOut = req.body.tokenOut.toLowerCase();
  }

  // Converte valores numéricos
  if (req.body.amountIn) {
    req.body.amountIn = parseFloat(req.body.amountIn);
  }

  if (req.body.slippage) {
    req.body.slippage = parseFloat(req.body.slippage);
  }

  next();
}

module.exports = {
  verifySignature,
  checkBalance,
  validateSwapParams,
  createRateLimiter,
  requestLogger,
  validateNetwork,
  sanitizeInput
};
