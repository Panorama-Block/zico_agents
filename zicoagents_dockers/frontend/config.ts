export const routerAddress = "0x111111125421cA6dc452d289314280a0f8842A65";
export const oneInchNativeToken = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE";

const getBackendUrl = () => {
  const host = process.env.NEXT_PUBLIC_API_URL;
  return host || 'http://localhost:8080';
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
