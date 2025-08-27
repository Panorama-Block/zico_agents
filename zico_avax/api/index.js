require("dotenv").config();
const express = require("express");
const { ethers } = require("ethers");
const { ThirdwebSDK } = require("@thirdweb-dev/sdk");
const cors = require("cors");
const fs = require("fs");

const app = express();
const port = 3000;
app.use(cors());
app.use(express.json());

const provider = new ethers.JsonRpcProvider(process.env.RPC_URL);
const sdk = ThirdwebSDK.fromPrivateKey(
  process.env.WALLET_PRIVATE_KEY, 
  provider,                       
  { secretKey: process.env.THIRDWEB_SECRET_KEY }
);

// ----------- Analysis Contract -----------
const analysisAbi = require("./abi/Analysis.json").abi;
const analysisContract = new ethers.Contract(process.env.CONTRACT_ADDRESS, analysisAbi, provider);

// ----------- Swap Contract -----------
const swapAbi = require("./abi/Swap.json").abi;
const swapContract = new ethers.Contract(process.env.SWAP_CONTRACT_ADDRESS, swapAbi, provider);

// ----------- Validation Contract ----------- 

const validationAbi = require("./abi/Validation.json").abi;
const validationContract = new ethers.Contract(process.env.VALIDATION_CONTRACT_ADDRESS, validationAbi, provider);

// ----------- Middleware de verificação de assinatura -----------
async function verifySignature(req, res, next) {
  try {
    const { address, signature, message } = req.body;

    if (!address || !signature || !message) {
      return res.status(400).json({ error: "Parâmetros inválidos" });
    }

    const recovered = ethers.verifyMessage(message, signature);
    if (recovered.toLowerCase() !== address.toLowerCase()) {
      return res.status(401).json({ error: "Assinatura inválida" });
    }

    // Passa para a rota
    next();
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Erro ao verificar assinatura" });
  }
}

// ----------- Rotas protegidas para Analysis -----------
app.post("/analysis/:pair", verifySignature, async (req, res) => {
  try {
    const pair = req.params.pair;
    const analysis = await analysisContract.makeAnalysis(pair);
    res.json({ pair, analysis });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Erro ao fazer análise", details: err.message });
  }
});

app.post("/price/chainlink/:pair", verifySignature, async (req, res) => {
  try {
    const pair = req.params.pair;
    const price = await analysisContract.getMediumPrice(pair);
    res.json({ pair, price: price.toString() });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Erro ao obter preço médio", details: err.message });
  }
});

// ----------- Rotas protegidas para Swap -----------
app.post("/swap/price/uniswap/:tokenA/:tokenB", verifySignature, async (req, res) => {
  try {
    const { tokenA, tokenB } = req.params;
    const price = await swapContract.getPriceInUniswap(tokenA, tokenB);
    res.json({ tokenA, tokenB, price: price.toString() });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Erro ao buscar preço no Uniswap", details: err.message });
  }
});

app.post("/swap/price/pangolin/:tokenA/:tokenB", verifySignature, async (req, res) => {
  try {
    const { tokenA, tokenB } = req.params;
    const price = await swapContract.getPriceInPangolin(tokenA, tokenB);
    res.json({ tokenA, tokenB, price: price.toString() });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Erro ao buscar preço no Pangolin", details: err.message });
  }
});

app.post("/swap/price/chainlink/:pair", verifySignature, async (req, res) => {
  try {
    const { pair } = req.params;
    const price = await swapContract.getMediumPrice(pair);
    res.json({ pair, price: price.toString() });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Erro ao buscar preço Chainlink", details: err.message });
  }
});

app.post("/swap/token-addresses/:pair", verifySignature, async (req, res) => {
  try {
    const pair = req.params.pair;
    const [tokenA, tokenB] = await swapContract.getTokenAddresses(pair);
    res.json({ pair, tokenA, tokenB });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Erro ao buscar endereços dos tokens", details: err.message });
  }
});

app.post("/swap/balance", verifySignature, async (req, res) => {
  try {
    const balance = await swapContract.balance();
    res.json({ balance: ethers.formatEther(balance) + " AVAX" });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Erro ao buscar balance", details: err.message });
  }
});

// ----------- Rotas protegidas para Validation -----------

app.post("/validation/tax-rate", verifySignature, async (req, res) => {
  try {
    const taxRate = await validationContract.taxRate();
    res.json({ taxRate: taxRate.toString() });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Erro ao buscar taxRate", details: err.message });
  }
});

app.post("/validation/owner", verifySignature, async (req, res) => {
  try {
    const owner = await validationContract.owner();
    res.json({ owner });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Erro ao buscar owner", details: err.message });
  }
});

app.post("/validation/calculate/:amount", verifySignature, async (req, res) => {
  try {
    const { amount } = req.params;
    const value = await validationContract.calculateValue(amount);
    res.json({ amount, value: value.toString() });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Erro ao calcular valor", details: err.message });
  }
});

app.post("/validation/pay", verifySignature, async (req, res) => {
  try {
    const { amount } = req.body;
    if (!amount) {
      return res.status(400).json({ error: "amount é obrigatório" });
    }

    const validationTw = await sdk.getContract(process.env.VALIDATION_CONTRACT_ADDRESS, validationAbi);

    const tx = await validationTw.call("payAndValidate", [], {
      value: ethers.parseEther(amount.toString())
    });

    res.json({ txHash: tx.receipt.transactionHash, status: "success" });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Erro em payAndValidate", details: err.message });
  }
});

app.post("/validation/set-tax", verifySignature, async (req, res) => {
  try {
    const { taxRate } = req.body;
    if (!taxRate) {
      return res.status(400).json({ error: "taxRate é obrigatório" });
    }

    const validationTw = await sdk.getContract(process.env.VALIDATION_CONTRACT_ADDRESS, validationAbi);

    const tx = await validationTw.call("setTaxRate", [taxRate]);
    res.json({ txHash: tx.receipt.transactionHash, status: "success" });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Erro ao atualizar taxRate", details: err.message });
  }
});

app.post("/validation/withdraw", verifySignature, async (req, res) => {
  try {
    const validationTw = await sdk.getContract(process.env.VALIDATION_CONTRACT_ADDRESS, validationAbi);

    const tx = await validationTw.call("withdraw");
    res.json({ txHash: tx.receipt.transactionHash, status: "success" });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Erro no withdraw", details: err.message });
  }
});

// ----------- Root Route -----------
app.get("/", (req, res) => {
  res.send("🟢 API de Análise & Swap funcionando com Thirdweb e assinaturas!");
});

app.listen(port, () => {
  console.log(`🚀 Servidor rodando em http://localhost:${port}`);
});