export const IStakingV2_ABI = [
  {
    "inputs": [
      {
        "internalType": "bytes32",
        "name": "delegate",
        "type": "bytes32"
      }
    ],
    "name": "addProxy",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "bytes32",
        "name": "hotkey",
        "type": "bytes32"
      },
      {
        "internalType": "uint256",
        "name": "amount",
        "type": "uint256"
      },
      {
        "internalType": "uint256",
        "name": "netuid",
        "type": "uint256"
      }
    ],
    "name": "addStake",
    "outputs": [],
    "stateMutability": "payable",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "bytes32",
        "name": "hotkey",
        "type": "bytes32"
      },
      {
        "internalType": "uint256",
        "name": "amount",
        "type": "uint256"
      },
      {
        "internalType": "uint256",
        "name": "limit_price",
        "type": "uint256"
      },
      {
        "internalType": "bool",
        "name": "allow_partial",
        "type": "bool"
      },
      {
        "internalType": "uint256",
        "name": "netuid",
        "type": "uint256"
      }
    ],
    "name": "addStakeLimit",
    "outputs": [],
    "stateMutability": "payable",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "bytes32",
        "name": "hotkey",
        "type": "bytes32"
      },
      {
        "internalType": "uint256",
        "name": "netuid",
        "type": "uint256"
      }
    ],
    "name": "getAlphaStakedValidators",
    "outputs": [
      {
        "internalType": "uint256[]",
        "name": "",
        "type": "uint256[]"
      }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "bytes32",
        "name": "hotkey",
        "type": "bytes32"
      },
      {
        "internalType": "bytes32",
        "name": "coldkey",
        "type": "bytes32"
      },
      {
        "internalType": "uint256",
        "name": "netuid",
        "type": "uint256"
      }
    ],
    "name": "getStake",
    "outputs": [
      {
        "internalType": "uint256",
        "name": "",
        "type": "uint256"
      }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "bytes32",
        "name": "hotkey",
        "type": "bytes32"
      },
      {
        "internalType": "uint256",
        "name": "netuid",
        "type": "uint256"
      }
    ],
    "name": "getTotalAlphaStaked",
    "outputs": [
      {
        "internalType": "uint256",
        "name": "",
        "type": "uint256"
      }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "bytes32",
        "name": "coldkey",
        "type": "bytes32"
      }
    ],
    "name": "getTotalColdkeyStake",
    "outputs": [
      {
        "internalType": "uint256",
        "name": "",
        "type": "uint256"
      }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "bytes32",
        "name": "hotkey",
        "type": "bytes32"
      }
    ],
    "name": "getTotalHotkeyStake",
    "outputs": [
      {
        "internalType": "uint256",
        "name": "",
        "type": "uint256"
      }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [],
    "name": "getNominatorMinRequiredStake",
    "outputs": [
      {
        "internalType": "uint256",
        "name": "",
        "type": "uint256"
      }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "bytes32",
        "name": "origin_hotkey",
        "type": "bytes32"
      },
      {
        "internalType": "bytes32",
        "name": "destination_hotkey",
        "type": "bytes32"
      },
      {
        "internalType": "uint256",
        "name": "origin_netuid",
        "type": "uint256"
      },
      {
        "internalType": "uint256",
        "name": "destination_netuid",
        "type": "uint256"
      },
      {
        "internalType": "uint256",
        "name": "amount",
        "type": "uint256"
      }
    ],
    "name": "moveStake",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "bytes32",
        "name": "delegate",
        "type": "bytes32"
      }
    ],
    "name": "removeProxy",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "bytes32",
        "name": "hotkey",
        "type": "bytes32"
      },
      {
        "internalType": "uint256",
        "name": "amount",
        "type": "uint256"
      },
      {
        "internalType": "uint256",
        "name": "netuid",
        "type": "uint256"
      }
    ],
    "name": "removeStake",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "bytes32",
        "name": "hotkey",
        "type": "bytes32"
      },
      {
        "internalType": "uint256",
        "name": "netuid",
        "type": "uint256"
      }
    ],
    "name": "removeStakeFull",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "bytes32",
        "name": "hotkey",
        "type": "bytes32"
      },
      {
        "internalType": "uint256",
        "name": "netuid",
        "type": "uint256"
      },
      {
        "internalType": "uint256",
        "name": "limitPrice",
        "type": "uint256"
      }
    ],
    "name": "removeStakeFullLimit",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "bytes32",
        "name": "hotkey",
        "type": "bytes32"
      },
      {
        "internalType": "uint256",
        "name": "amount",
        "type": "uint256"
      },
      {
        "internalType": "uint256",
        "name": "limit_price",
        "type": "uint256"
      },
      {
        "internalType": "bool",
        "name": "allow_partial",
        "type": "bool"
      },
      {
        "internalType": "uint256",
        "name": "netuid",
        "type": "uint256"
      }
    ],
    "name": "removeStakeLimit",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "bytes32",
        "name": "destination_coldkey",
        "type": "bytes32"
      },
      {
        "internalType": "bytes32",
        "name": "hotkey",
        "type": "bytes32"
      },
      {
        "internalType": "uint256",
        "name": "origin_netuid",
        "type": "uint256"
      },
      {
        "internalType": "uint256",
        "name": "destination_netuid",
        "type": "uint256"
      },
      {
        "internalType": "uint256",
        "name": "amount",
        "type": "uint256"
      }
    ],
    "name": "transferStake",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  }
]
