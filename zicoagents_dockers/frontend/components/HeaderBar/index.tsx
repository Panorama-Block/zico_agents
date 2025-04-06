import React, { FC, useState } from "react";
import { useRouter } from 'next/navigation'
import Image from "next/image";
import { Box, HStack, Spacer, Button, ButtonGroup, Text } from "@chakra-ui/react";
import { ConnectButton } from "@rainbow-me/rainbowkit";
import { CDPWallets } from "@/components/CDPWallets";
import classes from "./index.module.css";
import { Heading } from "lucide-react";
import { ArrowBackIcon } from "@chakra-ui/icons";

export const HeaderBar: FC = () => {
  const [walletType, setWalletType] = useState<"cdp" | "metamask">("cdp");
  const router = useRouter()

  return (
    <Box className={classes.headerBar}>
      <HStack spacing={4} width="100%" px={4}>
        <Box >
          <ArrowBackIcon color="gray.200" onClick={() => router.push("https://www.panoramablock.com")} />
        </Box>
        <Box className={classes.logo} flexShrink={0}>

          <a>
            <Image src="/assets/logo.png" alt="logo" width={30} height={40} />
          </a>
          <Text fontSize="md" color="white" marginLeft={5}> Zico Agent </Text>
        </Box>
        <Spacer />
        <HStack spacing={4} flexShrink={0}>
          {walletType === "cdp" ? <CDPWallets /> : <ConnectButton />}

          {/* Wallet Selection */}
          <ButtonGroup isAttached>
            <Button
              onClick={() => setWalletType("cdp")}
              bg={walletType === "cdp" ? "#56DBE0" : "ghost"}
              color={walletType === "cdp" ? "black" : "white"}
              sx={{
                "&:hover": {
                  transform: "none",
                  backgroundColor: "#63DAE0",
                  color: "black",
                },
                backgroundColor: walletType === "cdp" ? undefined : "gray.700",
              }}
            >
              CDP Managed Wallets
            </Button>
            <Button
              onClick={() => setWalletType("metamask")}
              bg={walletType === "metamask" ? "#56DBE0" : "gray.700"}
              color={walletType === "metamask" ? "black" : "white"}
              sx={{
                "&:hover": {
                  transform: "none",
                  backgroundColor: "#63DAE0",
                  color: "black",
                },
                backgroundColor:
                  walletType === "metamask" ? undefined : "gray.700",
              }}
            >
              Metamask
            </Button>
          </ButtonGroup>
        </HStack>
      </HStack>
    </Box>
  );
};
