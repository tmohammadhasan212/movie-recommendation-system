from __future__ import annotations

import torch
from torch import nn


class MatrixFactorization(nn.Module):
    def __init__(self, users: int, items: int, factors: int = 48) -> None:
        super().__init__()
        self.user_embeddings = nn.Embedding(users, factors)
        self.item_embeddings = nn.Embedding(items, factors)
        self.user_bias = nn.Embedding(users, 1)
        self.item_bias = nn.Embedding(items, 1)
        nn.init.normal_(self.user_embeddings.weight, std=0.05)
        nn.init.normal_(self.item_embeddings.weight, std=0.05)
        nn.init.zeros_(self.user_bias.weight)
        nn.init.zeros_(self.item_bias.weight)

    def forward(self, users: torch.Tensor, items: torch.Tensor) -> torch.Tensor:
        interaction = (self.user_embeddings(users) * self.item_embeddings(items)).sum(dim=1)
        return interaction + self.user_bias(users).squeeze(1) + self.item_bias(items).squeeze(1)
