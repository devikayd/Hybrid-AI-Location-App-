"""
Recommendation System Enhancements

Implements:
- Collaborative filtering (SVD matrix factorization)
- Hybrid recommendation (content + collaborative + context)
- Implicit feedback weighting (recency, interaction strength)
- Contextual bandits (explore-exploit for cold start)
- Diversity-aware re-ranking

All components have lightweight implementations suitable for resource-constrained environments.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime, timedelta
from collections import defaultdict
import math
import random

logger = logging.getLogger(__name__)

# Optional heavy dependencies
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    from scipy.sparse import csr_matrix
    from scipy.sparse.linalg import svds
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


class ImplicitFeedbackWeighter:
    """
    Weight user interactions based on recency and interaction type.

    More recent interactions and stronger signals (saves > likes > views)
    get higher weights.
    """

    # Interaction type weights (stronger signals = higher weight)
    INTERACTION_WEIGHTS = {
        'save': 1.0,
        'like': 0.7,
        'view': 0.3,
        'click': 0.2,
        'share': 0.9,
        'comment': 0.8,
    }

    # Recency decay parameters
    HALF_LIFE_DAYS = 7  # Weight halves every 7 days

    def __init__(self, half_life_days: int = 7):
        self.half_life_days = half_life_days

    def calculate_weight(
        self,
        interaction_type: str,
        interaction_time: datetime,
        current_time: Optional[datetime] = None
    ) -> float:
        """
        Calculate weight for a single interaction.

        Args:
            interaction_type: Type of interaction (like, save, view, etc.)
            interaction_time: When the interaction occurred
            current_time: Reference time (defaults to now)

        Returns:
            Float weight between 0 and 1
        """
        if current_time is None:
            current_time = datetime.utcnow()

        # Base weight from interaction type
        base_weight = self.INTERACTION_WEIGHTS.get(interaction_type.lower(), 0.3)

        # Apply recency decay (exponential decay)
        days_ago = (current_time - interaction_time).total_seconds() / 86400
        recency_factor = math.pow(0.5, days_ago / self.half_life_days)

        return base_weight * recency_factor

    def aggregate_weights(
        self,
        interactions: List[Dict[str, Any]],
        current_time: Optional[datetime] = None
    ) -> Dict[str, float]:
        """
        Aggregate weights for items based on all interactions.

        Args:
            interactions: List of interaction dicts with item_id, interaction_type, created_at
            current_time: Reference time

        Returns:
            Dict mapping item_id to aggregated weight
        """
        if current_time is None:
            current_time = datetime.utcnow()

        item_weights = defaultdict(float)

        for interaction in interactions:
            item_id = interaction.get('item_id')
            if not item_id:
                continue

            interaction_type = interaction.get('interaction_type', 'view')

            # Parse interaction time
            created_at = interaction.get('created_at')
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    created_at = current_time
            elif not isinstance(created_at, datetime):
                created_at = current_time

            weight = self.calculate_weight(interaction_type, created_at, current_time)
            item_weights[item_id] += weight

        return dict(item_weights)


class CollaborativeFilter:
    """
    Collaborative filtering using SVD matrix factorization.

    Learns latent factors from user-item interaction matrix to find
    similar users and recommend items they liked.
    """

    def __init__(self, n_factors: int = 20, min_interactions: int = 5):
        """
        Args:
            n_factors: Number of latent factors for SVD
            min_interactions: Minimum interactions needed to use collaborative filtering
        """
        self.n_factors = n_factors
        self.min_interactions = min_interactions

        # Matrices and mappings (set during fit)
        self.user_factors = None
        self.item_factors = None
        self.user_to_idx = {}
        self.idx_to_user = {}
        self.item_to_idx = {}
        self.idx_to_item = {}
        self._fitted = False

    def fit(self, interactions: List[Dict[str, Any]]) -> bool:
        """
        Fit the collaborative filter on interaction data.

        Args:
            interactions: List of dicts with user_id, item_id, weight (optional)

        Returns:
            True if fitting succeeded, False otherwise
        """
        if not NUMPY_AVAILABLE or not SCIPY_AVAILABLE:
            logger.warning("NumPy/SciPy not available, collaborative filtering disabled")
            return False

        if len(interactions) < self.min_interactions:
            logger.info(f"Insufficient interactions ({len(interactions)}) for collaborative filtering")
            return False

        try:
            # Build user and item mappings
            users = set()
            items = set()
            for interaction in interactions:
                users.add(interaction['user_id'])
                items.add(interaction['item_id'])

            self.user_to_idx = {u: i for i, u in enumerate(sorted(users))}
            self.idx_to_user = {i: u for u, i in self.user_to_idx.items()}
            self.item_to_idx = {it: i for i, it in enumerate(sorted(items))}
            self.idx_to_item = {i: it for it, i in self.item_to_idx.items()}

            n_users = len(users)
            n_items = len(items)

            if n_users < 2 or n_items < 2:
                logger.info("Not enough users/items for collaborative filtering")
                return False

            # Build sparse interaction matrix
            rows = []
            cols = []
            data = []

            for interaction in interactions:
                user_idx = self.user_to_idx[interaction['user_id']]
                item_idx = self.item_to_idx[interaction['item_id']]
                weight = interaction.get('weight', 1.0)

                rows.append(user_idx)
                cols.append(item_idx)
                data.append(weight)

            matrix = csr_matrix(
                (data, (rows, cols)),
                shape=(n_users, n_items)
            )

            # Perform SVD
            k = min(self.n_factors, min(n_users, n_items) - 1)
            if k < 1:
                return False

            U, sigma, Vt = svds(matrix.astype(float), k=k)

            # Store factors
            self.user_factors = U * np.sqrt(sigma)
            self.item_factors = Vt.T * np.sqrt(sigma)
            self._fitted = True

            logger.info(f"Collaborative filter fitted: {n_users} users, {n_items} items, {k} factors")
            return True

        except Exception as e:
            logger.warning(f"Collaborative filtering fit failed: {e}")
            return False

    def predict_score(self, user_id: str, item_id: str) -> float:
        """
        Predict user's preference score for an item.

        Args:
            user_id: User identifier
            item_id: Item identifier

        Returns:
            Predicted preference score (0 if unknown user/item)
        """
        if not self._fitted:
            return 0.0

        if user_id not in self.user_to_idx or item_id not in self.item_to_idx:
            return 0.0

        user_idx = self.user_to_idx[user_id]
        item_idx = self.item_to_idx[item_id]

        score = np.dot(self.user_factors[user_idx], self.item_factors[item_idx])
        return float(max(0.0, min(1.0, score)))  # Clamp to [0, 1]

    def get_similar_users(self, user_id: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """
        Find users most similar to given user.

        Args:
            user_id: User identifier
            top_k: Number of similar users to return

        Returns:
            List of (user_id, similarity) tuples
        """
        if not self._fitted or user_id not in self.user_to_idx:
            return []

        user_idx = self.user_to_idx[user_id]
        user_vec = self.user_factors[user_idx]

        similarities = []
        for other_idx in range(len(self.user_factors)):
            if other_idx == user_idx:
                continue
            other_vec = self.user_factors[other_idx]

            # Cosine similarity
            norm_product = np.linalg.norm(user_vec) * np.linalg.norm(other_vec)
            if norm_product > 0:
                sim = np.dot(user_vec, other_vec) / norm_product
                similarities.append((self.idx_to_user[other_idx], float(sim)))

        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]

    def recommend_items(
        self,
        user_id: str,
        exclude_items: Optional[Set[str]] = None,
        top_k: int = 10
    ) -> List[Tuple[str, float]]:
        """
        Recommend items for a user based on collaborative filtering.

        Args:
            user_id: User identifier
            exclude_items: Items to exclude (e.g., already interacted)
            top_k: Number of recommendations

        Returns:
            List of (item_id, score) tuples
        """
        if not self._fitted or user_id not in self.user_to_idx:
            return []

        exclude_items = exclude_items or set()

        scores = []
        for item_id in self.item_to_idx:
            if item_id in exclude_items:
                continue
            score = self.predict_score(user_id, item_id)
            scores.append((item_id, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


class ContextualBandit:
    """
    Epsilon-greedy contextual bandit for explore-exploit trade-off.

    Balances exploitation (recommending known good items) with
    exploration (trying new items to learn preferences).
    Especially useful for cold-start users.
    """

    def __init__(
        self,
        epsilon: float = 0.1,
        epsilon_decay: float = 0.99,
        min_epsilon: float = 0.01
    ):
        """
        Args:
            epsilon: Initial exploration rate (0-1)
            epsilon_decay: Decay factor applied per selection
            min_epsilon: Minimum exploration rate
        """
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.min_epsilon = min_epsilon

        # Track item performance
        self.item_rewards = defaultdict(list)  # item_id -> list of rewards

    def update_reward(self, item_id: str, reward: float):
        """
        Update reward for an item based on user feedback.

        Args:
            item_id: Item that was shown
            reward: Reward signal (e.g., 1 for click/like, 0 for ignore)
        """
        self.item_rewards[item_id].append(reward)

    def get_item_score(self, item_id: str) -> float:
        """
        Get average reward for an item.

        Args:
            item_id: Item identifier

        Returns:
            Average reward (0.5 for unknown items)
        """
        rewards = self.item_rewards.get(item_id, [])
        if not rewards:
            return 0.5  # Neutral score for unknown
        return sum(rewards) / len(rewards)

    def select_items(
        self,
        candidate_items: List[Dict[str, Any]],
        content_scores: Dict[str, float],
        n_items: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Select items using epsilon-greedy strategy.

        Args:
            candidate_items: List of candidate item dicts (must have 'id' field)
            content_scores: Content-based scores for items
            n_items: Number of items to select

        Returns:
            Selected items with exploration flag
        """
        if not candidate_items:
            return []

        selected = []
        remaining = list(candidate_items)

        for _ in range(min(n_items, len(remaining))):
            if not remaining:
                break

            # Decide: explore or exploit
            explore = random.random() < self.epsilon

            if explore:
                # Random selection (exploration)
                idx = random.randint(0, len(remaining) - 1)
                item = remaining.pop(idx)
                item['_explored'] = True
            else:
                # Best item selection (exploitation)
                best_idx = 0
                best_score = -float('inf')

                for i, item in enumerate(remaining):
                    item_id = item.get('id', str(i))

                    # Combine content score with bandit score
                    content = content_scores.get(item_id, 0.5)
                    bandit = self.get_item_score(item_id)
                    combined = 0.7 * content + 0.3 * bandit

                    if combined > best_score:
                        best_score = combined
                        best_idx = i

                item = remaining.pop(best_idx)
                item['_explored'] = False

            selected.append(item)

        # Decay epsilon
        self.epsilon = max(self.min_epsilon, self.epsilon * self.epsilon_decay)

        return selected


class DiversityReranker:
    """
    Re-rank recommendations to improve diversity.

    Uses Maximal Marginal Relevance (MMR) to balance relevance
    with diversity across item types, categories, and sources.
    """

    def __init__(self, lambda_param: float = 0.7):
        """
        Args:
            lambda_param: Trade-off between relevance (1.0) and diversity (0.0)
        """
        self.lambda_param = lambda_param

    def _calculate_similarity(
        self,
        item1: Dict[str, Any],
        item2: Dict[str, Any]
    ) -> float:
        """
        Calculate similarity between two items.

        Based on shared attributes (type, category, source).
        """
        similarity = 0.0

        # Type similarity (weight: 0.4)
        if item1.get('type') == item2.get('type'):
            similarity += 0.4

        # Category similarity (weight: 0.3)
        if item1.get('category') == item2.get('category'):
            similarity += 0.3

        # Source similarity (weight: 0.2)
        if item1.get('source') == item2.get('source'):
            similarity += 0.2

        # Subtype similarity (weight: 0.1)
        if item1.get('subtype') == item2.get('subtype'):
            similarity += 0.1

        return similarity

    def rerank(
        self,
        items: List[Dict[str, Any]],
        scores: Dict[str, float],
        n_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Re-rank items using MMR for diversity.

        Args:
            items: List of candidate items (must have 'id' field)
            scores: Relevance scores for items
            n_results: Number of items to return

        Returns:
            Re-ranked list of items
        """
        if not items:
            return []

        if len(items) <= n_results:
            # No need to rerank if we're keeping all items
            return sorted(items, key=lambda x: scores.get(x.get('id', ''), 0), reverse=True)

        selected = []
        remaining = list(items)

        for _ in range(n_results):
            if not remaining:
                break

            best_idx = 0
            best_mmr = -float('inf')

            for i, candidate in enumerate(remaining):
                item_id = candidate.get('id', str(i))
                relevance = scores.get(item_id, 0.0)

                # Calculate max similarity to already selected items
                if selected:
                    max_sim = max(
                        self._calculate_similarity(candidate, sel)
                        for sel in selected
                    )
                else:
                    max_sim = 0.0

                # MMR score
                mmr = self.lambda_param * relevance - (1 - self.lambda_param) * max_sim

                if mmr > best_mmr:
                    best_mmr = mmr
                    best_idx = i

            selected.append(remaining.pop(best_idx))

        return selected


class HybridRecommender:
    """
    Hybrid recommendation combining multiple strategies:
    - Content-based filtering
    - Collaborative filtering
    - Implicit feedback weighting
    - Contextual exploration
    - Diversity re-ranking
    """

    def __init__(
        self,
        content_weight: float = 0.4,
        collaborative_weight: float = 0.3,
        implicit_weight: float = 0.3,
        diversity_lambda: float = 0.7,
        exploration_rate: float = 0.1
    ):
        """
        Args:
            content_weight: Weight for content-based scores
            collaborative_weight: Weight for collaborative filtering scores
            implicit_weight: Weight for implicit feedback scores
            diversity_lambda: MMR lambda for diversity-relevance trade-off
            exploration_rate: Initial exploration rate for bandit
        """
        self.content_weight = content_weight
        self.collaborative_weight = collaborative_weight
        self.implicit_weight = implicit_weight

        # Initialize components
        self.implicit_weighter = ImplicitFeedbackWeighter()
        self.collaborative_filter = CollaborativeFilter()
        self.bandit = ContextualBandit(epsilon=exploration_rate)
        self.diversity_reranker = DiversityReranker(lambda_param=diversity_lambda)

        self._collab_fitted = False

    def fit_collaborative(self, all_interactions: List[Dict[str, Any]]) -> bool:
        """
        Fit collaborative filter on all user interactions.

        Args:
            all_interactions: List of all user-item interactions

        Returns:
            True if fitting succeeded
        """
        self._collab_fitted = self.collaborative_filter.fit(all_interactions)
        return self._collab_fitted

    def calculate_hybrid_scores(
        self,
        user_id: str,
        candidate_items: List[Dict[str, Any]],
        content_scores: Dict[str, float],
        user_interactions: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Calculate hybrid scores combining all signals.

        Args:
            user_id: User identifier
            candidate_items: Items to score
            content_scores: Pre-computed content-based scores
            user_interactions: User's interaction history

        Returns:
            Dict mapping item_id to hybrid score
        """
        # Get implicit feedback weights
        implicit_weights = self.implicit_weighter.aggregate_weights(user_interactions)

        # Normalize implicit weights
        max_implicit = max(implicit_weights.values()) if implicit_weights else 1.0
        if max_implicit > 0:
            implicit_weights = {k: v / max_implicit for k, v in implicit_weights.items()}

        hybrid_scores = {}

        for item in candidate_items:
            item_id = item.get('id', '')

            # Content score
            content_score = content_scores.get(item_id, 0.0)

            # Collaborative score
            if self._collab_fitted:
                collab_score = self.collaborative_filter.predict_score(user_id, item_id)
            else:
                collab_score = 0.0

            # Implicit feedback boost (higher weight for recently interacted similar items)
            implicit_score = implicit_weights.get(item_id, 0.0)

            # Calculate hybrid score
            if self._collab_fitted:
                hybrid = (
                    self.content_weight * content_score +
                    self.collaborative_weight * collab_score +
                    self.implicit_weight * implicit_score
                )
            else:
                # Without collaborative, redistribute weight
                adjusted_content = self.content_weight + self.collaborative_weight * 0.6
                adjusted_implicit = self.implicit_weight + self.collaborative_weight * 0.4
                hybrid = adjusted_content * content_score + adjusted_implicit * implicit_score

            hybrid_scores[item_id] = hybrid

        return hybrid_scores

    def recommend(
        self,
        user_id: str,
        candidate_items: List[Dict[str, Any]],
        content_scores: Dict[str, float],
        user_interactions: List[Dict[str, Any]],
        n_recommendations: int = 10,
        apply_diversity: bool = True,
        apply_exploration: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Generate recommendations using hybrid approach.

        Args:
            user_id: User identifier
            candidate_items: Items to consider
            content_scores: Content-based scores
            user_interactions: User's interaction history
            n_recommendations: Number of recommendations
            apply_diversity: Whether to apply diversity re-ranking
            apply_exploration: Whether to apply explore-exploit

        Returns:
            List of recommended items with scores
        """
        if not candidate_items:
            return []

        # Calculate hybrid scores
        hybrid_scores = self.calculate_hybrid_scores(
            user_id, candidate_items, content_scores, user_interactions
        )

        # Apply exploration if enabled and user is cold-start
        if apply_exploration and len(user_interactions) < 10:
            selected = self.bandit.select_items(
                candidate_items, hybrid_scores, n_recommendations * 2
            )
        else:
            selected = list(candidate_items)

        # Apply diversity re-ranking
        if apply_diversity:
            result = self.diversity_reranker.rerank(
                selected, hybrid_scores, n_recommendations
            )
        else:
            # Simple sorting by score
            result = sorted(
                selected,
                key=lambda x: hybrid_scores.get(x.get('id', ''), 0),
                reverse=True
            )[:n_recommendations]

        # Add scores to results
        for item in result:
            item_id = item.get('id', '')
            item['_hybrid_score'] = hybrid_scores.get(item_id, 0.0)

        return result

    def update_feedback(self, item_id: str, positive: bool):
        """
        Update bandit with user feedback.

        Args:
            item_id: Item that received feedback
            positive: Whether feedback was positive (like/save)
        """
        reward = 1.0 if positive else 0.0
        self.bandit.update_reward(item_id, reward)


# Singleton instance for global access
recommendation_enhancements = HybridRecommender()


def get_recommendation_status() -> Dict[str, Any]:
    """Get status of recommendation enhancements."""
    return {
        'collaborative_fitted': recommendation_enhancements._collab_fitted,
        'exploration_rate': recommendation_enhancements.bandit.epsilon,
        'numpy_available': NUMPY_AVAILABLE,
        'scipy_available': SCIPY_AVAILABLE,
        'components': {
            'implicit_feedback': True,
            'collaborative_filtering': NUMPY_AVAILABLE and SCIPY_AVAILABLE,
            'contextual_bandit': True,
            'diversity_reranking': True
        }
    }
