import '../styles/globals.css';
import '@rainbow-me/rainbowkit/styles.css';
import type { AppProps } from 'next/app';
import { background, ChakraProvider, defineStyleConfig, extendTheme } from '@chakra-ui/react'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { WagmiProvider } from 'wagmi';
import {
  arbitrum,
  base,
  avalanche,
  avalancheFuji,
  mainnet,
  optimism,
  polygon,
  sepolia,
  bsc,
} from 'wagmi/chains';
import { getDefaultConfig, RainbowKitProvider, darkTheme } from '@rainbow-me/rainbowkit';
import './../styles/globals.css';

const config = getDefaultConfig({
  appName: 'RainbowKit App',
  projectId: 'YOUR_PROJECT_ID',
  chains: [
    avalanche,
    avalancheFuji,
    mainnet,
    polygon,
    optimism,
    arbitrum,
    base,
    bsc,
    // ...(process.env.NEXT_PUBLIC_ENABLE_TESTNETS === 'true' ? [sepolia] : []),
  ],
  ssr: true,
});



const ButtonStyles = defineStyleConfig({
  variants: {
    greenCustom: {
      fontFamily: 'Inter',
      fontSize: '16px',
      background: '#59F886',
      borderRadius: '24px',
      color: 'var(--background-secondary)',
      '&:hover': {
        background: '#59F886',
        color: 'var(--background-secondary)',
        transform: 'scale(1.05)',
        boxShadow: '0px 4px 4px rgba(0, 0, 0, 0.25)',
        border: '1px solid #59F886'
      }
    }
  }
})

const theme = extendTheme({
  initialColorMode: 'dark',
  useSystemColorMode: false,
  colors: {
    'header': 'var(--background-secondary)',
    'pop-up-bg': '#1C201D',
  },
  components: {
    Button: ButtonStyles,
  },
  Text: {
    baseStyle: {
      fontFamily: 'Inter',
      fontSize: '16px',
      color: 'var(--dark-text-90, rgba(255, 255, 255, 0.90))'
    }
  },
})

const client = new QueryClient();

function MyApp({ Component, pageProps }: AppProps) {
  return (
    <WagmiProvider config={config}>
      <QueryClientProvider client={client}>
        <RainbowKitProvider theme={darkTheme({
          accentColor: '#111613',
          accentColorForeground: 'white',
          borderRadius: 'small',
          fontStack: 'system',
          overlayBlur: 'small',
        })}>
          <ChakraProvider theme={theme}>
            <Component {...pageProps} />
          </ChakraProvider>
        </RainbowKitProvider>
      </QueryClientProvider>
    </WagmiProvider>
  );
}

export default MyApp;
