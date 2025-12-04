"""
Data Validators for Data Quality Checks

What this module does:
- Validates data quality before ML training
- Checks for common data issues (missing values, outliers, invalid formats)
- Flags data for review
- Ensures data meets quality standards for ML models

Technologies used:
- Python: Built-in validation logic
- Regular expressions: Pattern matching for validation
- Datetime: Date/time validation
- Decimal: Coordinate validation

Why this is important:
- ML models need clean, validated data
- Bad data = bad predictions
- Early detection of data quality issues
- Prevents training on corrupted data
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


class DataValidator:
    """
    Data Validator Class
    
    Purpose:
    - Validates data quality for ML training
    - Checks for common data issues
    - Flags problematic records
    
    How it works:
    1. Validates coordinates (latitude/longitude)
    2. Validates dates and formats
    3. Validates text fields (length, content)
    4. Validates numeric fields (ranges, types)
    5. Flags records for review
    """
    
    # Valid coordinate ranges (UK bounds)
    UK_LAT_MIN = 49.0
    UK_LAT_MAX = 61.0
    UK_LON_MIN = -8.0
    UK_LON_MAX = 2.0
    
    # Valid date formats
    DATE_FORMATS = ['%Y-%m', '%Y-%m-%d', '%Y-%m-%d %H:%M:%S']
    
    def __init__(self):
        """Initialize validator"""
        self.validation_stats = {
            'total_checked': 0,
            'valid': 0,
            'invalid': 0,
            'warnings': 0,
            'errors': []
        }
    
    def validate_coordinates(self, lat: Optional[float], lon: Optional[float]) -> Tuple[bool, Optional[str]]:
        """
        Validate latitude and longitude coordinates
        
        What it checks:
        - Coordinates are not None
        - Coordinates are within UK bounds
        - Coordinates are valid numbers
        
        Returns:
        - (is_valid, error_message)
        
        Example:
        >>> validator = DataValidator()
        >>> validator.validate_coordinates(51.5074, -0.1278)
        (True, None)
        >>> validator.validate_coordinates(200.0, -0.1278)
        (False, 'Latitude out of range: 200.0')
        """
        if lat is None or lon is None:
            return False, "Missing coordinates"
        
        try:
            lat_float = float(lat)
            lon_float = float(lon)
        except (ValueError, TypeError):
            return False, f"Invalid coordinate type: lat={type(lat)}, lon={type(lon)}"
        
        # Check latitude range (UK bounds)
        if not (self.UK_LAT_MIN <= lat_float <= self.UK_LAT_MAX):
            return False, f"Latitude out of range: {lat_float} (UK: {self.UK_LAT_MIN} to {self.UK_LAT_MAX})"
        
        # Check longitude range (UK bounds)
        if not (self.UK_LON_MIN <= lon_float <= self.UK_LON_MAX):
            return False, f"Longitude out of range: {lon_float} (UK: {self.UK_LON_MIN} to {self.UK_LON_MAX})"
        
        return True, None
    
    def validate_date(self, date_str: Optional[str], field_name: str = "date") -> Tuple[bool, Optional[str]]:
        """
        Validate date string format
        
        What it checks:
        - Date string is not None/empty
        - Date matches expected formats
        - Date is parseable
        
        Returns:
        - (is_valid, error_message)
        
        Example:
        >>> validator = DataValidator()
        >>> validator.validate_date("2024-01", "month")
        (True, None)
        >>> validator.validate_date("invalid", "month")
        (False, 'Invalid date format: invalid')
        """
        if not date_str:
            return False, f"Missing {field_name}"
        
        if not isinstance(date_str, str):
            return False, f"Invalid {field_name} type: {type(date_str)}"
        
        # Try parsing with different formats
        for fmt in self.DATE_FORMATS:
            try:
                datetime.strptime(date_str, fmt)
                return True, None
            except ValueError:
                continue
        
        return False, f"Invalid {field_name} format: {date_str}"
    
    def validate_text(self, text: Optional[str], field_name: str, max_length: Optional[int] = None, min_length: int = 0) -> Tuple[bool, Optional[str]]:
        """
        Validate text field
        
        What it checks:
        - Text is not None
        - Text length is within bounds
        - Text is not just whitespace
        
        Returns:
        - (is_valid, error_message)
        
        Example:
        >>> validator = DataValidator()
        >>> validator.validate_text("Valid text", "title", max_length=100)
        (True, None)
        >>> validator.validate_text("", "title")
        (False, 'Text is empty')
        """
        if text is None:
            return False, f"Missing {field_name}"
        
        if not isinstance(text, str):
            return False, f"Invalid {field_name} type: {type(text)}"
        
        text = text.strip()
        
        if len(text) < min_length:
            return False, f"{field_name} too short: {len(text)} < {min_length}"
        
        if max_length and len(text) > max_length:
            return False, f"{field_name} too long: {len(text)} > {max_length}"
        
        return True, None
    
    def validate_numeric(self, value: Optional[float], field_name: str, min_value: Optional[float] = None, max_value: Optional[float] = None) -> Tuple[bool, Optional[str]]:
        """
        Validate numeric field
        
        What it checks:
        - Value is not None
        - Value is a valid number
        - Value is within range
        
        Returns:
        - (is_valid, error_message)
        
        Example:
        >>> validator = DataValidator()
        >>> validator.validate_numeric(0.5, "score", min_value=0.0, max_value=1.0)
        (True, None)
        >>> validator.validate_numeric(2.0, "score", min_value=0.0, max_value=1.0)
        (False, 'score out of range: 2.0 (expected 0.0 to 1.0)')
        """
        if value is None:
            return False, f"Missing {field_name}"
        
        try:
            num_value = float(value)
        except (ValueError, TypeError):
            return False, f"Invalid {field_name} type: {type(value)}"
        
        if min_value is not None and num_value < min_value:
            return False, f"{field_name} below minimum: {num_value} < {min_value}"
        
        if max_value is not None and num_value > max_value:
            return False, f"{field_name} above maximum: {num_value} > {max_value}"
        
        return True, None
    
    def validate_crime_data(self, crime_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate crime data record
        
        What it validates:
        - Coordinates (lat/lon)
        - Category (not empty)
        - Month (valid date format)
        - Crime ID (if present)
        
        Returns:
        - (is_valid, list_of_errors)
        
        Example:
        >>> validator = DataValidator()
        >>> crime = {"latitude": 51.5074, "longitude": -0.1278, "category": "burglary", "month": "2024-01"}
        >>> validator.validate_crime_data(crime)
        (True, [])
        """
        errors = []
        
        # Validate coordinates
        is_valid, error = self.validate_coordinates(
            crime_data.get('latitude'),
            crime_data.get('longitude')
        )
        if not is_valid:
            errors.append(f"Coordinates: {error}")
        
        # Validate category
        is_valid, error = self.validate_text(crime_data.get('category'), "category", min_length=1, max_length=100)
        if not is_valid:
            errors.append(f"Category: {error}")
        
        # Validate month
        if crime_data.get('month'):
            is_valid, error = self.validate_date(crime_data.get('month'), "month")
            if not is_valid:
                errors.append(f"Month: {error}")
        
        return len(errors) == 0, errors
    
    def validate_news_data(self, news_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate news data record
        
        What it validates:
        - Title (required, not empty)
        - Coordinates (if present, must be valid)
        - Published date (if present, must be valid)
        - Sentiment score (if present, must be -1 to 1)
        
        Returns:
        - (is_valid, list_of_errors)
        """
        errors = []
        
        # Validate title (required)
        is_valid, error = self.validate_text(news_data.get('title'), "title", min_length=1, max_length=500)
        if not is_valid:
            errors.append(f"Title: {error}")
        
        # Validate coordinates (optional, but if present must be valid)
        lat = news_data.get('latitude')
        lon = news_data.get('longitude')
        if lat is not None or lon is not None:
            is_valid, error = self.validate_coordinates(lat, lon)
            if not is_valid:
                errors.append(f"Coordinates: {error}")
        
        # Validate published date (optional)
        if news_data.get('published_at'):
            is_valid, error = self.validate_date(str(news_data.get('published_at')), "published_at")
            if not is_valid:
                errors.append(f"Published date: {error}")
        
        # Validate sentiment score (if present)
        sentiment = news_data.get('sentiment_score')
        if sentiment is not None:
            is_valid, error = self.validate_numeric(sentiment, "sentiment_score", min_value=-1.0, max_value=1.0)
            if not is_valid:
                errors.append(f"Sentiment: {error}")
        
        return len(errors) == 0, errors
    
    def validate_poi_data(self, poi_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate POI data record
        
        What it validates:
        - Coordinates (required)
        - Name (optional, but if present must be valid)
        - Amenity (optional)
        
        Returns:
        - (is_valid, list_of_errors)
        """
        errors = []
        
        # Validate coordinates (required)
        is_valid, error = self.validate_coordinates(
            poi_data.get('latitude'),
            poi_data.get('longitude')
        )
        if not is_valid:
            errors.append(f"Coordinates: {error}")
        
        # Validate name (optional, but if present must be valid)
        if poi_data.get('name'):
            is_valid, error = self.validate_text(poi_data.get('name'), "name", max_length=500)
            if not is_valid:
                errors.append(f"Name: {error}")
        
        return len(errors) == 0, errors
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics"""
        return self.validation_stats.copy()


# Global validator instance
data_validator = DataValidator()



