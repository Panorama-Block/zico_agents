class Metadata:
    def __init__(self):
        self.crypto_data_agent = {}
        self.swap_agent = {}

    def get_crypto_data_agent(self):
        return self.crypto_data_agent
    
    def set_crypto_data_agent(self, crypto_data_agent):
        self.crypto_data_agent = crypto_data_agent

    def get_swap_agent(self):
        return self.swap_agent
    
    def set_swap_agent(self, swap_agent):
        self.swap_agent = swap_agent

metadata = Metadata()