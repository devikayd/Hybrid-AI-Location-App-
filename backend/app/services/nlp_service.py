"""
NLP service for sentiment analysis, keyword extraction, and NER

Enhanced with:
- Aspect-based sentiment analysis
- Text embeddings & semantic similarity
- Topic modelling
- Temporal sentiment trends
- Enhanced entity extraction
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
import asyncio
from functools import lru_cache

# Import NLP libraries
try:
    import nltk
    from nltk.sentiment import SentimentIntensityAnalyzer
    from nltk.corpus import stopwords
    from nltk.tokenize import word_tokenize
    from nltk.stem import WordNetLemmatizer
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

# Import NLP enhancements
try:
    from app.ml.nlp_enhancements import (
        nlp_enhancements,
        AspectSentimentAnalyzer,
        TextEmbedder,
        TopicModeler,
        TemporalSentimentTracker,
        EnhancedEntityExtractor,
        check_nlp_dependencies
    )
    NLP_ENHANCEMENTS_AVAILABLE = True
except ImportError:
    NLP_ENHANCEMENTS_AVAILABLE = False

from app.core.config import settings
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


class NLPService:
    """NLP service for text analysis"""
    
    def __init__(self):
        self.vader_analyzer = None
        self.nlp_model = None
        self.stop_words = set()
        self.lemmatizer = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize NLP models and resources"""
        if self._initialized:
            return
        
        try:
            await self._download_nltk_data()
            await self._initialize_models()
            self._initialized = True
            logger.info("NLP service initialized successfully")
        except Exception as e:
            logger.error(f"NLP service initialization failed: {e}")
            raise AppException(f"NLP initialization failed: {str(e)}")
    
    async def _download_nltk_data(self):
        """Download required NLTK data"""
        if not NLTK_AVAILABLE:
            logger.warning("NLTK not available, skipping data download")
            return
        
        try:
            # Download required NLTK data
            nltk_data = [
                'vader_lexicon',
                'punkt',
                'stopwords',
                'wordnet',
                'averaged_perceptron_tagger'
            ]
            
            for data in nltk_data:
                try:
                    nltk.data.find(f'tokenizers/{data}')
                except LookupError:
                    logger.info(f"Downloading NLTK data: {data}")
                    nltk.download(data, quiet=True)
            
            logger.info("NLTK data download completed")
        except Exception as e:
            logger.warning(f"NLTK data download failed: {e}")
    
    async def _initialize_models(self):
        """Initialize NLP models"""
        if NLTK_AVAILABLE:
            try:
                self.vader_analyzer = SentimentIntensityAnalyzer()
                self.stop_words = set(stopwords.words('english'))
                self.lemmatizer = WordNetLemmatizer()
                logger.info("NLTK models initialized")
            except Exception as e:
                logger.warning(f"NLTK model initialization failed: {e}")
        
        if SPACY_AVAILABLE:
            try:
                # Try to load English model
                self.nlp_model = spacy.load("en_core_web_sm")
                logger.info("spaCy model loaded")
            except OSError:
                logger.warning("spaCy English model not found, trying alternative")
                try:
                    self.nlp_model = spacy.load("en_core_web_md")
                    logger.info("spaCy medium model loaded")
                except OSError:
                    logger.warning("spaCy models not available")
                    self.nlp_model = None
    
    async def analyze_sentiment(self, text: str) -> Dict[str, float]:
        """
        Analyze sentiment of text using VADER
        Returns sentiment scores: positive, negative, neutral, compound
        """
        if not self._initialized:
            await self.initialize()
        
        if not self.vader_analyzer:
            # Fallback to simple keyword-based sentiment
            return self._simple_sentiment(text)
        
        try:
            scores = self.vader_analyzer.polarity_scores(text)
            return {
                "positive": scores["pos"],
                "negative": scores["neg"],
                "neutral": scores["neu"],
                "compound": scores["compound"]
            }
        except Exception as e:
            logger.warning(f"VADER sentiment analysis failed: {e}")
            return self._simple_sentiment(text)
    
    def _simple_sentiment(self, text: str) -> Dict[str, float]:
        """Simple keyword-based sentiment analysis fallback"""
        positive_words = {
            "good", "great", "excellent", "amazing", "wonderful", "fantastic",
            "positive", "success", "win", "gain", "rise", "up", "happy",
            "love", "best", "perfect", "outstanding", "brilliant"
        }
        negative_words = {
            "bad", "terrible", "awful", "horrible", "negative", "fail",
            "loss", "drop", "down", "crisis", "problem", "issue", "error",
            "hate", "worst", "disappointing", "sad", "angry", "frustrated"
        }
        
        text_lower = text.lower()
        words = text_lower.split()
        
        positive_count = sum(1 for word in words if word in positive_words)
        negative_count = sum(1 for word in words if word in negative_words)
        total_words = len(words)
        
        if total_words == 0:
            return {"positive": 0.0, "negative": 0.0, "neutral": 1.0, "compound": 0.0}
        
        positive_score = positive_count / total_words
        negative_score = negative_count / total_words
        neutral_score = 1.0 - positive_score - negative_score
        compound_score = positive_score - negative_score
        
        return {
            "positive": positive_score,
            "negative": negative_score,
            "neutral": max(0.0, neutral_score),
            "compound": compound_score
        }
    
    async def extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """
        Extract keywords from text using spaCy or NLTK
        """
        if not self._initialized:
            await self.initialize()
        
        if self.nlp_model:
            return self._extract_keywords_spacy(text, max_keywords)
        elif NLTK_AVAILABLE:
            return self._extract_keywords_nltk(text, max_keywords)
        else:
            return self._extract_keywords_simple(text, max_keywords)
    
    def _extract_keywords_spacy(self, text: str, max_keywords: int) -> List[str]:
        """Extract keywords using spaCy"""
        try:
            doc = self.nlp_model(text)
            keywords = []
            
            for token in doc:
                if (token.is_alpha and 
                    not token.is_stop and 
                    not token.is_punct and
                    len(token.text) > 2 and
                    token.pos_ in ["NOUN", "ADJ", "VERB"]):
                    keywords.append(token.lemma_.lower())
            
            # Remove duplicates and return top keywords
            unique_keywords = list(dict.fromkeys(keywords))
            return unique_keywords[:max_keywords]
        except Exception as e:
            logger.warning(f"spaCy keyword extraction failed: {e}")
            return self._extract_keywords_simple(text, max_keywords)
    
    def _extract_keywords_nltk(self, text: str, max_keywords: int) -> List[str]:
        """Extract keywords using NLTK"""
        try:
            tokens = word_tokenize(text.lower())
            keywords = []
            
            for token in tokens:
                if (token.isalpha() and 
                    token not in self.stop_words and
                    len(token) > 2):
                    lemmatized = self.lemmatizer.lemmatize(token)
                    keywords.append(lemmatized)
            
            # Remove duplicates and return top keywords
            unique_keywords = list(dict.fromkeys(keywords))
            return unique_keywords[:max_keywords]
        except Exception as e:
            logger.warning(f"NLTK keyword extraction failed: {e}")
            return self._extract_keywords_simple(text, max_keywords)
    
    def _extract_keywords_simple(self, text: str, max_keywords: int) -> List[str]:
        """Simple keyword extraction fallback"""
        # Remove punctuation and split into words
        words = [word.lower().strip(".,!?;:") for word in text.split()]
        
        # Filter out common words and short words
        common_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
        keywords = [word for word in words if word not in common_words and len(word) > 2]
        
        # Count frequency and return most common
        word_freq = {}
        for word in keywords:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        sorted_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, freq in sorted_keywords[:max_keywords]]
    
    async def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract named entities from text using spaCy
        """
        if not self._initialized:
            await self.initialize()
        
        if not self.nlp_model:
            return []
        
        try:
            doc = self.nlp_model(text)
            entities = []
            
            for ent in doc.ents:
                entities.append({
                    "text": ent.text,
                    "label": ent.label_,
                    "start": ent.start_char,
                    "end": ent.end_char,
                    "description": spacy.explain(ent.label_) or "Unknown"
                })
            
            return entities
        except Exception as e:
            logger.warning(f"Entity extraction failed: {e}")
            return []
    
    async def summarize_text(self, text: str, max_sentences: int = 3) -> str:
        """
        Generate a simple extractive summary of text
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # Split into sentences
            sentences = text.split('. ')
            if len(sentences) <= max_sentences:
                return text
            
            # Score sentences based on word frequency
            word_freq = {}
            for sentence in sentences:
                words = sentence.lower().split()
                for word in words:
                    word_freq[word] = word_freq.get(word, 0) + 1
            
            # Score sentences
            sentence_scores = []
            for sentence in sentences:
                words = sentence.lower().split()
                score = sum(word_freq.get(word, 0) for word in words)
                sentence_scores.append((score, sentence))
            
            # Sort by score and take top sentences
            sentence_scores.sort(reverse=True)
            top_sentences = [sentence for score, sentence in sentence_scores[:max_sentences]]
            
            # Return in original order
            summary_sentences = []
            for sentence in sentences:
                if sentence in top_sentences:
                    summary_sentences.append(sentence)
            
            return '. '.join(summary_sentences) + '.'
        except Exception as e:
            logger.warning(f"Text summarization failed: {e}")
            return text[:200] + "..." if len(text) > 200 else text

    # =========================================================================
    # ENHANCED NLP METHODS (NLP Improvements)
    # =========================================================================

    async def analyze_aspect_sentiment(self, text: str) -> Dict[str, Any]:
        """
        Analyze sentiment for specific aspects (safety, amenities, etc.)

        Args:
            text: Input text to analyze

        Returns:
            Dict with sentiment per aspect and overall analysis
        """
        if not self._initialized:
            await self.initialize()

        if NLP_ENHANCEMENTS_AVAILABLE:
            try:
                return nlp_enhancements.aspect_analyzer.analyze(text)
            except Exception as e:
                logger.warning(f"Aspect sentiment analysis failed: {e}")

        # Fallback to basic sentiment
        basic_sentiment = await self.analyze_sentiment(text)
        return {
            'aspects': {},
            'overall_sentiment': basic_sentiment.get('compound', 0),
            'dominant_aspect': None,
            'aspect_coverage': 0,
            'fallback': True
        }

    async def find_similar_texts(
        self,
        query: str,
        candidates: List[str],
        top_k: int = 5
    ) -> List[Tuple[int, float]]:
        """
        Find texts most similar to query using semantic embeddings.

        Args:
            query: Query text
            candidates: List of candidate texts
            top_k: Number of results

        Returns:
            List of (index, similarity_score) tuples
        """
        if not self._initialized:
            await self.initialize()

        if NLP_ENHANCEMENTS_AVAILABLE:
            try:
                if not nlp_enhancements._initialized:
                    nlp_enhancements.initialize()
                return nlp_enhancements.embedder.find_similar(query, candidates, top_k)
            except Exception as e:
                logger.warning(f"Semantic similarity failed: {e}")

        # Fallback to simple word overlap
        results = []
        query_words = set(query.lower().split())
        for i, candidate in enumerate(candidates):
            cand_words = set(candidate.lower().split())
            if query_words and cand_words:
                overlap = len(query_words & cand_words) / len(query_words | cand_words)
                results.append((i, overlap))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    async def extract_topics(self, texts: List[str]) -> Dict[str, Any]:
        """
        Extract topics from a collection of texts.

        Args:
            texts: List of text documents

        Returns:
            Dict with topics and assignments
        """
        if not self._initialized:
            await self.initialize()

        if NLP_ENHANCEMENTS_AVAILABLE:
            try:
                if not nlp_enhancements._initialized:
                    nlp_enhancements.initialize()
                return nlp_enhancements.topic_modeler.fit_transform(texts)
            except Exception as e:
                logger.warning(f"Topic extraction failed: {e}")

        # Fallback: return empty topics
        return {
            'topics': [],
            'assignments': [],
            'error': 'Topic modelling not available'
        }

    async def analyze_sentiment_trends(
        self,
        articles: List[Dict[str, Any]],
        date_field: str = 'published_at',
        text_field: str = 'title'
    ) -> Dict[str, Any]:
        """
        Analyze sentiment trends over time.

        Args:
            articles: List of article dicts
            date_field: Name of date field
            text_field: Name of text field

        Returns:
            Dict with trend analysis
        """
        if not self._initialized:
            await self.initialize()

        if NLP_ENHANCEMENTS_AVAILABLE:
            try:
                return nlp_enhancements.trend_tracker.analyze_trends(
                    articles, date_field, text_field
                )
            except Exception as e:
                logger.warning(f"Trend analysis failed: {e}")

        # Fallback
        return {
            'timeline': [],
            'trend': {'direction': 'unknown', 'magnitude': 0},
            'significant_events': [],
            'error': 'Trend analysis not available'
        }

    async def analyze_articles(
        self,
        articles: List[Dict[str, Any]],
        text_field: str = 'title',
        date_field: str = 'published_at'
    ) -> Dict[str, Any]:
        """
        Run comprehensive NLP analysis on articles.

        Includes: topics, trends, aggregate aspect sentiment.

        Args:
            articles: List of article dicts
            text_field: Field containing text
            date_field: Field containing date

        Returns:
            Comprehensive analysis results
        """
        if not self._initialized:
            await self.initialize()

        if NLP_ENHANCEMENTS_AVAILABLE:
            try:
                if not nlp_enhancements._initialized:
                    nlp_enhancements.initialize()
                return nlp_enhancements.analyze_articles(
                    articles, text_field, date_field
                )
            except Exception as e:
                logger.warning(f"Article analysis failed: {e}")

        # Fallback
        return {
            'article_count': len(articles),
            'error': 'Enhanced analysis not available'
        }

    def get_enhancement_status(self) -> Dict[str, Any]:
        """Get status of NLP enhancements."""
        if NLP_ENHANCEMENTS_AVAILABLE:
            return nlp_enhancements.get_status()
        return {
            'initialized': False,
            'available': False,
            'message': 'NLP enhancements not installed'
        }


# Global NLP service instance
nlp_service = NLPService()






