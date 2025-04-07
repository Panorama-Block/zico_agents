export const routerAddress = "0x111111125421cA6dc452d289314280a0f8842A65";
export const oneInchNativeToken = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE";

const getBackendUrl = () => {
  if (typeof window !== 'undefined') {
    const protocol = window.location.protocol;
    const hostname = window.location.hostname;
    return `${protocol}//${hostname}:8080`;
  }

  return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';
};

export const availableAgents: {
  [key: string]: {
    name: string;
    description: string;
    endpoint: string;
    requirements: {
      connectedWallet: boolean;
    };
    supportsFiles?: boolean;
  };
} = {
  "swap-agent": {
    name: "Morpheus",
    description:
      "performs multiple tasks crypto data agent,swap agent and rag agent",
    endpoint: getBackendUrl(),
    requirements: {
      connectedWallet: true,
    },
    supportsFiles: true,
  },
};
