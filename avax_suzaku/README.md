# Suzaku Collateral

This repository contains a Suzaku Collateral interface and its default implementation.

It is a fork of [symbioticfi/collateral](https://github.com/symbioticfi/collateral).

## Collateral

**Collateral** is a concept introduced by [Symbiotic](https://symbiotic.fi) that brings capital efficiency and scale by enabling assets used to secure networks to be held outside of the restaking protocol itself - e.g. in DeFi positions on networks other than Ethereum itself.

The Collateral interface can be found [here](./src/interfaces/ICollateral.sol).

## Default Collateral

Default Collateral is a simple version of Collateral that has an instant debt repayment, which supports only non-rebase underlying assets.

The implementation can be found [here](./src/contracts/defaultCollateral).

## Security

Security audits can be found in the [symbioticfi/collateral](https://github.com/symbioticfi/collateral/tree/main/audits) repository.

## Usage

### Env

Create `.env` file using a template:

```
ETH_RPC_URL=
```

To get the `ETH_RPC_URL`, you can use [Alchemy](https://www.alchemy.com/), [Infura](https://infura.io/), or any other Ethereum node provider.

### Build

```shell
forge build
```

### Test

```shell
forge test
```

### Format

```shell
forge fmt
```

### Gas Snapshots

```shell
forge snapshot
```
