"""
NLP Enhancements Module

This module contains advanced NLP improvements:

1. Topic Modelling - Extract themes from news articles using BERTopic
2. Text Embeddings - Semantic similarity using sentence-transformers
3. Aspect-Based Sentiment - Sentiment per aspect (safety, amenities, etc.)
4. Temporal Sentiment Trends - Track sentiment changes over time
5. Enhanced Entity Extraction - Better NER with context

Author: MSc Data Science Project
Note: Heavy dependencies (BERTopic, sentence-transformers) are optional
      with lightweight fallbacks for resource-constrained environments.
"""

import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np

logger = logging.getLogger(__name__)

# =============================================================================
# OPTIONAL HEAVY DEPENDENCIES (with fallbacks)
# =============================================================================

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except (ImportError, OSError):
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.info("sentence-transformers not available. Using lightweight alternatives.")

try:
    from bertopic import BERTopic
    BERTOPIC_AVAILABLE = True
except (ImportError, OSError):
    BERTOPIC_AVAILABLE = False
    logger.info("BERTopic not available. Using LDA fallback for topic modelling.")

try:
    from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
    from sklearn.decomposition import LatentDirichletAllocation, NMF
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

# Try to use existing NLTK/spaCy from nlp_service
try:
    from nltk.sentiment import SentimentIntensityAnalyzer
    from nltk.tokenize import word_tokenize, sent_tokenize
    from nltk.corpus import stopwords
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False


# =============================================================================
# 1. ASPECT-BASED SENTIMENT ANALYSIS
# =============================================================================

class AspectSentimentAnalyzer:
    """
    Aspect-Based Sentiment Analysis

    Purpose:
        Analyzes sentiment for specific aspects of a location like safety,
        amenities, transport, etc. instead of overall sentiment.

    Why it matters:
        - "Great restaurants but unsafe at night" has mixed sentiment
        - Overall sentiment would average this out
        - Aspect sentiment captures nuance per category
    """

    # Define aspects and their associated keywords
    ASPECTS = {
        'safety': {
            'keywords': ['safe', 'unsafe', 'dangerous', 'crime', 'criminal', 'theft',
                        'robbery', 'assault', 'security', 'police', 'violent', 'peaceful',
                        'secure', 'risky', 'threatening', 'protected', 'vulnerable'],
            'weight': 1.5  # Safety is important for location assessment
        },
        'amenities': {
            'keywords': ['restaurant', 'cafe', 'shop', 'store', 'supermarket', 'mall',
                        'park', 'gym', 'library', 'hospital', 'pharmacy', 'bank',
                        'amenity', 'facility', 'service', 'convenience'],
            'weight': 1.0
        },
        'transport': {
            'keywords': ['bus', 'train', 'tube', 'metro', 'underground', 'station',
                        'transport', 'commute', 'traffic', 'parking', 'accessible',
                        'connected', 'journey', 'travel', 'rail', 'tram'],
            'weight': 1.0
        },
        'entertainment': {
            'keywords': ['event', 'concert', 'festival', 'theatre', 'cinema', 'museum',
                        'gallery', 'nightlife', 'club', 'pub', 'bar', 'entertainment',
                        'fun', 'activity', 'leisure', 'recreation'],
            'weight': 0.8
        },
        'environment': {
            'keywords': ['clean', 'dirty', 'pollution', 'green', 'park', 'nature',
                        'quiet', 'noisy', 'peaceful', 'crowded', 'spacious', 'beautiful',
                        'ugly', 'pleasant', 'environment', 'air', 'litter'],
            'weight': 0.9
        },
        'cost': {
            'keywords': ['expensive', 'cheap', 'affordable', 'price', 'cost', 'rent',
                        'budget', 'value', 'overpriced', 'reasonable', 'free',
                        'pricey', 'economical', 'luxury'],
            'weight': 0.8
        }
    }

    def __init__(self):
        """Initialize with VADER sentiment analyzer."""
        self.vader = None
        if NLTK_AVAILABLE:
            try:
                self.vader = SentimentIntensityAnalyzer()
            except Exception as e:
                logger.warning(f"VADER initialization failed: {e}")

    def analyze(self, text: str) -> Dict[str, Any]:
        """
        Analyze sentiment for each aspect in the text.

        Args:
            text: Input text to analyze

        Returns:
            Dict with aspect scores and overall analysis
        """
        if not text:
            return self._empty_result()

        text_lower = text.lower()
        sentences = self._split_sentences(text)

        aspect_results = {}

        for aspect, config in self.ASPECTS.items():
            aspect_sentences = self._find_aspect_sentences(
                sentences, config['keywords']
            )

            if aspect_sentences:
                sentiment = self._calculate_sentiment(aspect_sentences)
                aspect_results[aspect] = {
                    'sentiment': sentiment,
                    'confidence': min(1.0, len(aspect_sentences) / 3),
                    'sentence_count': len(aspect_sentences),
                    'weighted_score': sentiment * config['weight']
                }
            else:
                aspect_results[aspect] = {
                    'sentiment': 0.0,
                    'confidence': 0.0,
                    'sentence_count': 0,
                    'weighted_score': 0.0
                }

        # Calculate overall weighted sentiment
        weighted_scores = [r['weighted_score'] for r in aspect_results.values()
                         if r['confidence'] > 0]
        weights = [self.ASPECTS[a]['weight'] for a, r in aspect_results.items()
                  if r['confidence'] > 0]

        if weighted_scores and weights:
            overall = sum(weighted_scores) / sum(weights)
        else:
            # Fallback to full text sentiment
            overall = self._calculate_sentiment([text])

        return {
            'aspects': aspect_results,
            'overall_sentiment': overall,
            'dominant_aspect': self._get_dominant_aspect(aspect_results),
            'aspect_coverage': sum(1 for r in aspect_results.values() if r['confidence'] > 0)
        }

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        if NLTK_AVAILABLE:
            try:
                return sent_tokenize(text)
            except:
                pass
        # Fallback
        return [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]

    def _find_aspect_sentences(self, sentences: List[str], keywords: List[str]) -> List[str]:
        """Find sentences containing aspect keywords."""
        matching = []
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(kw in sentence_lower for kw in keywords):
                matching.append(sentence)
        return matching

    def _calculate_sentiment(self, texts: List[str]) -> float:
        """Calculate average sentiment for texts."""
        if not texts:
            return 0.0

        if self.vader:
            scores = []
            for text in texts:
                try:
                    score = self.vader.polarity_scores(text)['compound']
                    scores.append(score)
                except:
                    pass
            if scores:
                return sum(scores) / len(scores)

        # Simple keyword fallback
        return self._simple_sentiment(texts)

    def _simple_sentiment(self, texts: List[str]) -> float:
        """Simple keyword-based sentiment fallback."""
        positive = {'good', 'great', 'excellent', 'amazing', 'wonderful', 'best',
                   'love', 'fantastic', 'brilliant', 'safe', 'clean', 'beautiful'}
        negative = {'bad', 'terrible', 'awful', 'horrible', 'worst', 'hate',
                   'dangerous', 'dirty', 'ugly', 'crime', 'unsafe', 'poor'}

        pos_count = neg_count = 0
        for text in texts:
            words = text.lower().split()
            pos_count += sum(1 for w in words if w in positive)
            neg_count += sum(1 for w in words if w in negative)

        total = pos_count + neg_count
        if total == 0:
            return 0.0
        return (pos_count - neg_count) / total

    def _get_dominant_aspect(self, results: Dict) -> Optional[str]:
        """Get the aspect with highest confidence and sentiment magnitude."""
        max_score = 0
        dominant = None
        for aspect, data in results.items():
            score = abs(data['sentiment']) * data['confidence']
            if score > max_score:
                max_score = score
                dominant = aspect
        return dominant

    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure."""
        return {
            'aspects': {a: {'sentiment': 0.0, 'confidence': 0.0,
                          'sentence_count': 0, 'weighted_score': 0.0}
                       for a in self.ASPECTS},
            'overall_sentiment': 0.0,
            'dominant_aspect': None,
            'aspect_coverage': 0
        }


# =============================================================================
# 2. TEXT EMBEDDINGS & SEMANTIC SIMILARITY
# =============================================================================

class TextEmbedder:
    """
    Text Embeddings for Semantic Similarity

    Purpose:
        Creates dense vector representations of text for semantic search
        and similarity comparison.

    Why it matters:
        - "Is it safe here?" and "Is this area dangerous?" are semantically related
        - Keyword matching would miss this connection
        - Embeddings capture semantic meaning

    Note:
        Uses sentence-transformers if available, falls back to TF-IDF.
    """

    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        """
        Initialize embedder.

        Args:
            model_name: sentence-transformers model (small model for low memory)
        """
        self.model = None
        self.model_name = model_name
        self.tfidf = None
        self.use_transformers = False

    def initialize(self) -> bool:
        """Initialize the embedding model."""
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                logger.info(f"Loading sentence-transformers model: {self.model_name}")
                self.model = SentenceTransformer(self.model_name)
                self.use_transformers = True
                logger.info("Sentence-transformers model loaded successfully")
                return True
            except Exception as e:
                logger.warning(f"Failed to load sentence-transformers: {e}")

        # Fallback to TF-IDF
        if SKLEARN_AVAILABLE:
            logger.info("Using TF-IDF fallback for embeddings")
            self.tfidf = TfidfVectorizer(max_features=500, stop_words='english')
            return True

        logger.warning("No embedding method available")
        return False

    def embed(self, texts: List[str]) -> Optional[np.ndarray]:
        """
        Generate embeddings for texts.

        Args:
            texts: List of text strings

        Returns:
            Numpy array of embeddings (n_texts, embedding_dim)
        """
        if not texts:
            return None

        if self.use_transformers and self.model:
            try:
                return self.model.encode(texts, convert_to_numpy=True)
            except Exception as e:
                logger.warning(f"Transformer embedding failed: {e}")

        if self.tfidf:
            try:
                # Fit and transform
                if not hasattr(self.tfidf, 'vocabulary_'):
                    return self.tfidf.fit_transform(texts).toarray()
                return self.tfidf.transform(texts).toarray()
            except Exception as e:
                logger.warning(f"TF-IDF embedding failed: {e}")

        return None

    def similarity(self, text1: str, text2: str) -> float:
        """
        Calculate semantic similarity between two texts.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score (0-1)
        """
        embeddings = self.embed([text1, text2])
        if embeddings is None:
            return self._simple_similarity(text1, text2)

        # Cosine similarity
        if SKLEARN_AVAILABLE:
            sim = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
            return float(max(0, min(1, sim)))

        # Manual cosine similarity
        dot = np.dot(embeddings[0], embeddings[1])
        norm1 = np.linalg.norm(embeddings[0])
        norm2 = np.linalg.norm(embeddings[1])
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(max(0, min(1, dot / (norm1 * norm2))))

    def find_similar(self, query: str, candidates: List[str], top_k: int = 5) -> List[Tuple[int, float]]:
        """
        Find most similar texts to query.

        Args:
            query: Query text
            candidates: List of candidate texts
            top_k: Number of results to return

        Returns:
            List of (index, similarity_score) tuples
        """
        if not candidates:
            return []

        all_texts = [query] + candidates
        embeddings = self.embed(all_texts)

        if embeddings is None:
            return [(i, self._simple_similarity(query, c))
                   for i, c in enumerate(candidates)][:top_k]

        query_emb = embeddings[0]
        candidate_embs = embeddings[1:]

        # Calculate similarities
        similarities = []
        for i, cand_emb in enumerate(candidate_embs):
            if SKLEARN_AVAILABLE:
                sim = cosine_similarity([query_emb], [cand_emb])[0][0]
            else:
                dot = np.dot(query_emb, cand_emb)
                norm1 = np.linalg.norm(query_emb)
                norm2 = np.linalg.norm(cand_emb)
                sim = dot / (norm1 * norm2) if norm1 > 0 and norm2 > 0 else 0
            similarities.append((i, float(sim)))

        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]

    def _simple_similarity(self, text1: str, text2: str) -> float:
        """Simple word overlap similarity fallback."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union)


# =============================================================================
# 3. TOPIC MODELLING
# =============================================================================

class TopicModeler:
    """
    Topic Modelling for News/Text Analysis

    Purpose:
        Automatically discovers themes/topics in news articles
        to understand what's being discussed about a location.

    Why it matters:
        - Identifies trending topics (development, crime spree, events)
        - Groups similar articles
        - Shows location-specific themes

    Note:
        Uses BERTopic if available, falls back to LDA.
    """

    def __init__(self, n_topics: int = 10):
        """
        Initialize topic modeler.

        Args:
            n_topics: Number of topics to extract
        """
        self.n_topics = n_topics
        self.model = None
        self.use_bertopic = False
        self.vectorizer = None
        self.lda_model = None
        self.feature_names = None

    def initialize(self) -> bool:
        """Initialize the topic model."""
        if BERTOPIC_AVAILABLE:
            try:
                # Use lightweight embedding model
                if SENTENCE_TRANSFORMERS_AVAILABLE:
                    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                    self.model = BERTopic(
                        embedding_model=embedding_model,
                        nr_topics=self.n_topics,
                        verbose=False
                    )
                else:
                    self.model = BERTopic(nr_topics=self.n_topics, verbose=False)
                self.use_bertopic = True
                logger.info("BERTopic initialized")
                return True
            except Exception as e:
                logger.warning(f"BERTopic initialization failed: {e}")

        # Fallback to LDA
        if SKLEARN_AVAILABLE:
            logger.info("Using LDA fallback for topic modelling")
            self.vectorizer = CountVectorizer(
                max_features=1000,
                stop_words='english',
                min_df=2,
                max_df=0.95
            )
            self.lda_model = LatentDirichletAllocation(
                n_components=self.n_topics,
                random_state=42,
                max_iter=10
            )
            return True

        logger.warning("No topic modelling method available")
        return False

    def fit_transform(self, texts: List[str]) -> Dict[str, Any]:
        """
        Extract topics from texts.

        Args:
            texts: List of text documents

        Returns:
            Dict with topics, assignments, and metadata
        """
        if len(texts) < 5:
            return {
                'topics': [],
                'assignments': [],
                'error': 'Insufficient documents for topic modelling (need >= 5)'
            }

        if self.use_bertopic and self.model:
            return self._bertopic_extract(texts)
        elif self.lda_model:
            return self._lda_extract(texts)
        else:
            return self._simple_extract(texts)

    def _bertopic_extract(self, texts: List[str]) -> Dict[str, Any]:
        """Extract topics using BERTopic."""
        try:
            topics, probs = self.model.fit_transform(texts)
            topic_info = self.model.get_topic_info()

            # Format topics
            formatted_topics = []
            for _, row in topic_info.iterrows():
                if row['Topic'] != -1:  # Skip outlier topic
                    topic_words = self.model.get_topic(row['Topic'])
                    formatted_topics.append({
                        'id': int(row['Topic']),
                        'name': row.get('Name', f"Topic {row['Topic']}"),
                        'count': int(row['Count']),
                        'words': [w for w, _ in topic_words[:10]] if topic_words else []
                    })

            return {
                'topics': formatted_topics,
                'assignments': [int(t) for t in topics],
                'method': 'bertopic',
                'n_topics': len(formatted_topics)
            }
        except Exception as e:
            logger.error(f"BERTopic extraction failed: {e}")
            return self._lda_extract(texts) if self.lda_model else self._simple_extract(texts)

    def _lda_extract(self, texts: List[str]) -> Dict[str, Any]:
        """Extract topics using LDA."""
        try:
            # Vectorize
            doc_term_matrix = self.vectorizer.fit_transform(texts)
            self.feature_names = self.vectorizer.get_feature_names_out()

            # Fit LDA
            doc_topics = self.lda_model.fit_transform(doc_term_matrix)

            # Get topic words
            formatted_topics = []
            for topic_idx, topic in enumerate(self.lda_model.components_):
                top_word_indices = topic.argsort()[:-11:-1]
                top_words = [self.feature_names[i] for i in top_word_indices]
                formatted_topics.append({
                    'id': topic_idx,
                    'name': f"Topic {topic_idx}: {', '.join(top_words[:3])}",
                    'count': int(np.sum(doc_topics.argmax(axis=1) == topic_idx)),
                    'words': top_words
                })

            # Get assignments
            assignments = doc_topics.argmax(axis=1).tolist()

            return {
                'topics': formatted_topics,
                'assignments': assignments,
                'method': 'lda',
                'n_topics': len(formatted_topics)
            }
        except Exception as e:
            logger.error(f"LDA extraction failed: {e}")
            return self._simple_extract(texts)

    def _simple_extract(self, texts: List[str]) -> Dict[str, Any]:
        """Simple keyword clustering fallback."""
        # Define basic topic categories
        categories = {
            'crime': ['crime', 'police', 'arrest', 'theft', 'robbery', 'assault', 'violence'],
            'development': ['development', 'construction', 'building', 'project', 'plan', 'new'],
            'events': ['event', 'festival', 'concert', 'exhibition', 'show', 'celebration'],
            'business': ['business', 'company', 'shop', 'restaurant', 'opening', 'closed'],
            'transport': ['traffic', 'road', 'train', 'bus', 'transport', 'station'],
            'community': ['community', 'local', 'residents', 'council', 'meeting', 'neighbourhood']
        }

        topic_counts = {cat: 0 for cat in categories}
        assignments = []

        for text in texts:
            text_lower = text.lower()
            assigned = 'other'
            max_matches = 0

            for cat, keywords in categories.items():
                matches = sum(1 for kw in keywords if kw in text_lower)
                if matches > max_matches:
                    max_matches = matches
                    assigned = cat

            assignments.append(assigned)
            if assigned in topic_counts:
                topic_counts[assigned] += 1

        formatted_topics = [
            {
                'id': i,
                'name': cat,
                'count': count,
                'words': categories.get(cat, [])
            }
            for i, (cat, count) in enumerate(topic_counts.items()) if count > 0
        ]

        return {
            'topics': formatted_topics,
            'assignments': assignments,
            'method': 'keyword',
            'n_topics': len(formatted_topics)
        }


# =============================================================================
# 4. TEMPORAL SENTIMENT TRENDS
# =============================================================================

class TemporalSentimentTracker:
    """
    Temporal Sentiment Trend Analysis

    Purpose:
        Tracks how sentiment about a location changes over time,
        enabling trend detection and alerts.

    Why it matters:
        - Detect improving/declining areas
        - Identify sentiment spikes (events, incidents)
        - Show historical context
    """

    def __init__(self):
        """Initialize tracker."""
        self.vader = None
        if NLTK_AVAILABLE:
            try:
                self.vader = SentimentIntensityAnalyzer()
            except:
                pass

    def analyze_trends(
        self,
        articles: List[Dict[str, Any]],
        date_field: str = 'published_at',
        text_field: str = 'title',
        window_days: int = 7
    ) -> Dict[str, Any]:
        """
        Analyze sentiment trends over time.

        Args:
            articles: List of article dicts with date and text fields
            date_field: Name of date field in articles
            text_field: Name of text field to analyze
            window_days: Rolling window size in days

        Returns:
            Dict with trend data and analysis
        """
        if not articles:
            return self._empty_result()

        # Parse and sort by date
        dated_articles = []
        for article in articles:
            date_str = article.get(date_field)
            text = article.get(text_field, '')

            if not date_str or not text:
                continue

            date = self._parse_date(date_str)
            if date:
                sentiment = self._get_sentiment(text)
                dated_articles.append({
                    'date': date,
                    'sentiment': sentiment,
                    'text': text[:100]
                })

        if not dated_articles:
            return self._empty_result()

        # Sort by date
        dated_articles.sort(key=lambda x: x['date'])

        # Calculate daily averages
        daily_sentiment = defaultdict(list)
        for article in dated_articles:
            day_key = article['date'].strftime('%Y-%m-%d')
            daily_sentiment[day_key].append(article['sentiment'])

        daily_averages = {
            day: sum(scores) / len(scores)
            for day, scores in daily_sentiment.items()
        }

        # Calculate rolling average
        sorted_days = sorted(daily_averages.keys())
        rolling_avg = []

        for i, day in enumerate(sorted_days):
            window_start = max(0, i - window_days + 1)
            window_values = [daily_averages[sorted_days[j]]
                           for j in range(window_start, i + 1)]
            rolling_avg.append({
                'date': day,
                'sentiment': daily_averages[day],
                'rolling_avg': sum(window_values) / len(window_values)
            })

        # Calculate trend
        if len(rolling_avg) >= 2:
            first_half = [r['rolling_avg'] for r in rolling_avg[:len(rolling_avg)//2]]
            second_half = [r['rolling_avg'] for r in rolling_avg[len(rolling_avg)//2:]]

            first_avg = sum(first_half) / len(first_half) if first_half else 0
            second_avg = sum(second_half) / len(second_half) if second_half else 0

            trend_direction = 'improving' if second_avg > first_avg + 0.1 else \
                             'declining' if second_avg < first_avg - 0.1 else 'stable'
            trend_magnitude = abs(second_avg - first_avg)
        else:
            trend_direction = 'insufficient_data'
            trend_magnitude = 0

        # Find significant events (sentiment spikes)
        events = self._find_sentiment_spikes(rolling_avg)

        return {
            'timeline': rolling_avg,
            'trend': {
                'direction': trend_direction,
                'magnitude': trend_magnitude,
                'description': self._describe_trend(trend_direction, trend_magnitude)
            },
            'significant_events': events,
            'overall_sentiment': sum(daily_averages.values()) / len(daily_averages),
            'article_count': len(dated_articles),
            'date_range': {
                'start': sorted_days[0] if sorted_days else None,
                'end': sorted_days[-1] if sorted_days else None
            }
        }

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime."""
        if isinstance(date_str, datetime):
            return date_str

        formats = [
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d',
            '%d/%m/%Y',
            '%m/%d/%Y'
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str[:19], fmt[:len(date_str)])
            except:
                continue
        return None

    def _get_sentiment(self, text: str) -> float:
        """Get sentiment score for text."""
        if self.vader:
            try:
                return self.vader.polarity_scores(text)['compound']
            except:
                pass

        # Simple fallback
        positive = {'good', 'great', 'excellent', 'positive', 'success'}
        negative = {'bad', 'terrible', 'negative', 'fail', 'crime'}

        words = text.lower().split()
        pos = sum(1 for w in words if w in positive)
        neg = sum(1 for w in words if w in negative)

        if pos + neg == 0:
            return 0.0
        return (pos - neg) / (pos + neg)

    def _find_sentiment_spikes(self, timeline: List[Dict]) -> List[Dict]:
        """Find significant sentiment spikes."""
        if len(timeline) < 3:
            return []

        sentiments = [t['sentiment'] for t in timeline]
        mean = sum(sentiments) / len(sentiments)
        std = (sum((s - mean) ** 2 for s in sentiments) / len(sentiments)) ** 0.5

        if std == 0:
            return []

        events = []
        for t in timeline:
            z_score = (t['sentiment'] - mean) / std
            if abs(z_score) > 1.5:  # 1.5 standard deviations
                events.append({
                    'date': t['date'],
                    'sentiment': t['sentiment'],
                    'type': 'positive_spike' if z_score > 0 else 'negative_spike',
                    'magnitude': abs(z_score)
                })

        return events

    def _describe_trend(self, direction: str, magnitude: float) -> str:
        """Generate human-readable trend description."""
        if direction == 'improving':
            if magnitude > 0.3:
                return "Sentiment is significantly improving"
            return "Sentiment is gradually improving"
        elif direction == 'declining':
            if magnitude > 0.3:
                return "Sentiment is significantly declining"
            return "Sentiment is gradually declining"
        elif direction == 'stable':
            return "Sentiment remains stable"
        return "Insufficient data to determine trend"

    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure."""
        return {
            'timeline': [],
            'trend': {
                'direction': 'insufficient_data',
                'magnitude': 0,
                'description': 'No data available for trend analysis'
            },
            'significant_events': [],
            'overall_sentiment': 0,
            'article_count': 0,
            'date_range': {'start': None, 'end': None}
        }


# =============================================================================
# 5. ENHANCED ENTITY EXTRACTION
# =============================================================================

class EnhancedEntityExtractor:
    """
    Enhanced Named Entity Extraction

    Purpose:
        Extracts and categorizes entities with location relevance scoring.

    Improvements over basic NER:
        - Location-specific entity types
        - Relevance scoring
        - Entity deduplication
        - Context extraction
    """

    # Location-relevant entity types
    LOCATION_ENTITIES = {
        'GPE': 'geopolitical_entity',  # Cities, countries
        'LOC': 'location',              # Mountains, rivers
        'FAC': 'facility',              # Buildings, airports
        'ORG': 'organization',          # Companies, agencies
        'EVENT': 'event',               # Named events
        'PERSON': 'person'              # People
    }

    def __init__(self):
        """Initialize extractor."""
        self.nlp = None
        try:
            import spacy
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except:
                pass
        except ImportError:
            pass

    def extract(self, text: str, include_context: bool = True) -> Dict[str, Any]:
        """
        Extract entities from text.

        Args:
            text: Input text
            include_context: Include surrounding context for each entity

        Returns:
            Dict with entities grouped by type
        """
        if not text:
            return {'entities': {}, 'count': 0}

        if self.nlp:
            return self._spacy_extract(text, include_context)
        return self._simple_extract(text)

    def _spacy_extract(self, text: str, include_context: bool) -> Dict[str, Any]:
        """Extract using spaCy."""
        try:
            doc = self.nlp(text)

            entities_by_type = defaultdict(list)
            seen = set()

            for ent in doc.ents:
                # Deduplicate
                key = (ent.text.lower(), ent.label_)
                if key in seen:
                    continue
                seen.add(key)

                entity_type = self.LOCATION_ENTITIES.get(ent.label_, 'other')

                entity_data = {
                    'text': ent.text,
                    'type': entity_type,
                    'label': ent.label_,
                    'start': ent.start_char,
                    'end': ent.end_char
                }

                if include_context:
                    # Get surrounding context
                    start = max(0, ent.start_char - 50)
                    end = min(len(text), ent.end_char + 50)
                    entity_data['context'] = text[start:end].strip()

                entities_by_type[entity_type].append(entity_data)

            return {
                'entities': dict(entities_by_type),
                'count': sum(len(v) for v in entities_by_type.values()),
                'method': 'spacy'
            }
        except Exception as e:
            logger.warning(f"spaCy extraction failed: {e}")
            return self._simple_extract(text)

    def _simple_extract(self, text: str) -> Dict[str, Any]:
        """Simple regex-based entity extraction fallback."""
        entities = defaultdict(list)

        # Find capitalized phrases (potential entities)
        pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'
        matches = re.findall(pattern, text)

        seen = set()
        for match in matches:
            if match.lower() in seen:
                continue
            if len(match) > 2:  # Skip short matches
                seen.add(match.lower())
                entities['unknown'].append({
                    'text': match,
                    'type': 'unknown',
                    'label': 'UNKNOWN'
                })

        return {
            'entities': dict(entities),
            'count': len(entities.get('unknown', [])),
            'method': 'regex'
        }


# =============================================================================
# MAIN INTERFACE
# =============================================================================

class NLPEnhancements:
    """
    Main interface for all NLP enhancements.

    Provides unified access to:
    - Aspect-based sentiment analysis
    - Text embeddings & similarity
    - Topic modelling
    - Temporal sentiment trends
    - Enhanced entity extraction
    """

    def __init__(self):
        """Initialize all enhancement components."""
        self.aspect_analyzer = AspectSentimentAnalyzer()
        self.embedder = TextEmbedder()
        self.topic_modeler = TopicModeler()
        self.trend_tracker = TemporalSentimentTracker()
        self.entity_extractor = EnhancedEntityExtractor()
        self._initialized = False

    def initialize(self) -> Dict[str, bool]:
        """
        Initialize all components.

        Returns:
            Dict showing which components initialized successfully
        """
        status = {
            'aspect_sentiment': True,  # Always available (has fallbacks)
            'embeddings': self.embedder.initialize(),
            'topic_modelling': self.topic_modeler.initialize(),
            'temporal_trends': True,  # Always available
            'entity_extraction': self.entity_extractor.nlp is not None
        }

        self._initialized = True
        logger.info(f"NLP Enhancements initialized: {status}")
        return status

    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Run all analyses on a single text.

        Args:
            text: Input text

        Returns:
            Comprehensive analysis results
        """
        if not self._initialized:
            self.initialize()

        return {
            'aspect_sentiment': self.aspect_analyzer.analyze(text),
            'entities': self.entity_extractor.extract(text)
        }

    def analyze_articles(
        self,
        articles: List[Dict[str, Any]],
        text_field: str = 'title',
        date_field: str = 'published_at'
    ) -> Dict[str, Any]:
        """
        Run full analysis on a collection of articles.

        Args:
            articles: List of article dicts
            text_field: Field containing text to analyze
            date_field: Field containing date

        Returns:
            Comprehensive analysis including topics and trends
        """
        if not self._initialized:
            self.initialize()

        texts = [a.get(text_field, '') for a in articles if a.get(text_field)]

        results = {
            'article_count': len(texts)
        }

        # Topic modelling
        if texts:
            results['topics'] = self.topic_modeler.fit_transform(texts)

        # Temporal trends
        results['trends'] = self.trend_tracker.analyze_trends(
            articles, date_field, text_field
        )

        # Aggregate aspect sentiment
        aspect_results = [self.aspect_analyzer.analyze(t) for t in texts]
        if aspect_results:
            results['aggregate_aspects'] = self._aggregate_aspects(aspect_results)

        return results

    def _aggregate_aspects(self, results: List[Dict]) -> Dict[str, Any]:
        """Aggregate aspect sentiments across multiple texts."""
        aggregated = {}

        for aspect in AspectSentimentAnalyzer.ASPECTS:
            sentiments = [r['aspects'][aspect]['sentiment']
                         for r in results if r['aspects'][aspect]['confidence'] > 0]
            if sentiments:
                aggregated[aspect] = {
                    'avg_sentiment': sum(sentiments) / len(sentiments),
                    'count': len(sentiments),
                    'positive_pct': sum(1 for s in sentiments if s > 0.1) / len(sentiments),
                    'negative_pct': sum(1 for s in sentiments if s < -0.1) / len(sentiments)
                }

        return aggregated

    def get_status(self) -> Dict[str, Any]:
        """Get status of all NLP enhancement components."""
        return {
            'initialized': self._initialized,
            'components': {
                'aspect_sentiment': {
                    'available': True,
                    'vader_available': self.aspect_analyzer.vader is not None
                },
                'embeddings': {
                    'available': self.embedder.model is not None or self.embedder.tfidf is not None,
                    'method': 'sentence-transformers' if self.embedder.use_transformers else 'tfidf'
                },
                'topic_modelling': {
                    'available': self.topic_modeler.model is not None or self.topic_modeler.lda_model is not None,
                    'method': 'bertopic' if self.topic_modeler.use_bertopic else 'lda'
                },
                'temporal_trends': {
                    'available': True
                },
                'entity_extraction': {
                    'available': True,
                    'spacy_available': self.entity_extractor.nlp is not None
                }
            },
            'dependencies': {
                'sentence_transformers': SENTENCE_TRANSFORMERS_AVAILABLE,
                'bertopic': BERTOPIC_AVAILABLE,
                'sklearn': SKLEARN_AVAILABLE,
                'nltk': NLTK_AVAILABLE
            }
        }


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def check_nlp_dependencies() -> Dict[str, bool]:
    """Check which NLP dependencies are available."""
    return {
        'sentence_transformers': SENTENCE_TRANSFORMERS_AVAILABLE,
        'bertopic': BERTOPIC_AVAILABLE,
        'sklearn': SKLEARN_AVAILABLE,
        'nltk': NLTK_AVAILABLE
    }


# Global instance
nlp_enhancements = NLPEnhancements()
