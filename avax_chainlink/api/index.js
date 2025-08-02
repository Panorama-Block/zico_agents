require("dotenv").config();
const express = require("express");
const { ethers } = require("ethers");
const { JsonRpcProvider, formatEther } = require("ethers");
const cors = require("cors");
const fs = require("fs");

const app = express();
const port = 3000;
app.use(cors());

const provider = new JsonRpcProvider(process.env.RPC_URL);

// ----------- Analysis Contract -----------
const analysisAbi = require("./abi/Analysis.json").abi;
const analysisContract = new ethers.Contract(process.env.CONTRACT_ADDRESS, analysisAbi, provider);

// ----------- Swap Contract -----------
const swapAbi = require("./abi/Swap.json").abi;
const swapContract = new ethers.Contract(process.env.SWAP_CONTRACT_ADDRESS, swapAbi, provider);

// ----------- Routes for Analysis -----------
app.get("/analysis/:pair", async (req, res) => {
  try {
    const pair = req.params.pair;
    const analysis = await analysisContract.makeAnalysis(pair);
    res.json({ pair, analysis });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Erro ao fazer análise", details: err.message });
  }
});

app.get("/price/chainlink/:pair", async (req, res) => {
  try {
    const pair = req.params.pair;
    const price = await analysisContract.getMediumPrice(pair);
    res.json({ pair, price: price.toString() });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Erro ao obter preço médio", details: err.message });
  }
});

// ----------- Routes for Swap -----------

app.get("/swap/price/uniswap/:tokenA/:tokenB", async (req, res) => {
  try {
    const { tokenA, tokenB } = req.params;
    const price = await swapContract.getPriceInUniswap(tokenA, tokenB);
    res.json({ tokenA, tokenB, price: price.toString() });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Erro ao buscar preço no Uniswap", details: err.message });
  }
});

app.get("/swap/price/pangolin/:tokenA/:tokenB", async (req, res) => {
  try {
    const { tokenA, tokenB } = req.params;
    const price = await swapContract.getPriceInPangolin(tokenA, tokenB);
    res.json({ tokenA, tokenB, price: price.toString() });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Erro ao buscar preço no Pangolin", details: err.message });
  }
});

app.get("/swap/price/chainlink/:pair", async (req, res) => {
  try {
    const { pair } = req.params;
    const price = await swapContract.getMediumPrice(pair);
    res.json({ pair, price: price.toString() });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Erro ao buscar preço Chainlink", details: err.message });
  }
});

app.get("/swap/token-addresses/:pair", async (req, res) => {
  try {
    const pair = req.params.pair;
    const [tokenA, tokenB] = await swapContract.getTokenAddresses(pair);
    res.json({ pair, tokenA, tokenB });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Erro ao buscar endereços dos tokens", details: err.message });
  }
});

app.get("/swap/balance", async (req, res) => {
  try {
    const balance = await swapContract.balance(); 
    res.json({ balance: formatEther(balance) + " AVAX" });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Erro ao buscar balance", details: err.message });
  }
});

// ----------- Root Route -----------
app.get("/", (req, res) => {
  res.send("🟢 API de Análise & Swap funcionando!");
});

app.listen(port, () => {
  console.log(`🚀 Servidor rodando em http://localhost:${port}`);
});
