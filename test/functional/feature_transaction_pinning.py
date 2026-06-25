#!/usr/bin/env python3
# References: 
# Transaction Pinning: https://bitcoinops.org/en/topics/transaction-pinning/
# BIP 125 (RBF): https://github.com/bitcoin/bips/blob/master/bip-0125.mediawiki
# TRUC (BIP 431): https://github.com/bitcoin/bips/blob/master/bip-0431.mediawiki

from test_framework.test_framework import BitcoinTestFramework
from test_framework.wallet import MiniWallet
from test_framework.util import assert_raises_rpc_error
from decimal import Decimal

class TransactionPinningTest(BitcoinTestFramework):
    def set_test_params(self):
        self.num_nodes = 1
        self.setup_clean_chain = True

    def run_test(self):
        node = self.nodes[0]
        wallet = MiniWallet(node)

        self.log.info("Funding wallet...")
        self.generate(wallet, 101)
        
        utxo_alice = wallet.get_utxo()

        self.log.info("1. Alice broadcasts her original transaction (Tx A)")
        tx_a = wallet.create_self_transfer(utxo_to_spend=utxo_alice, fee_rate=Decimal("0.00010"))
        txid_a = node.sendrawtransaction(tx_a['hex'])
        
        # We need the UTXO created by Tx A so the attacker can spend it
        utxo_attacker = tx_a["new_utxo"]

        self.log.info("2. Attacker broadcasts a massive child transaction (Tx A_Child)")
        tx_a_child = wallet.create_self_transfer(
            utxo_to_spend=utxo_attacker, 
            fee_rate=Decimal("0.00001"), 
            target_vsize=100000 
        )
        node.sendrawtransaction(tx_a_child['hex'])

        self.log.info("3. Alice attempts to RBF Tx A with a higher fee rate (Tx B)")
        tx_b = wallet.create_self_transfer(
            utxo_to_spend=utxo_alice, 
            fee_rate=Decimal("0.00050") 
        )

        # Alice's Tx B has a 5x higher fee RATE (50 vs 10). 
        # However, due to BIP 125 Rule 3, it must pay a higher ABSOLUTE fee 
        # than Tx A + Tx A_Child combined. Since Tx A_Child is huge, this fails.
        self.log.info("Asserting node rejects Tx B due to insufficient absolute fee")
        
        assert_raises_rpc_error(
            -26, 
            "insufficient fee", 
            node.sendrawtransaction, 
            tx_b['hex']
        )
        self.log.info("Pinning attack successful! Tx B was rejected.")

        self.log.info("4. Challenge: Overcome the Pin!")
        # Challenge 1: Calculate exactly how much fee `tx_b` needs to successfully 
        # replace the package, and recreate tx_b to succeed.
        # 
        # Challenge 2 (Advanced): Look at `mempool_truc.py`. Modify Tx A and Tx B
        # to use TRUC (version=3). TRUC rules limit child sizes, which prevents 
        # this specific pinning vector entirely.

if __name__ == '__main__':
    TransactionPinningTest(__file__).main()