"""Fact validation service for verifying LLM-generated content against database."""

import re
import logging
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime
from sqlalchemy.orm import Session

from ..models.post import Post
from ..models.link import Link

logger = logging.getLogger(__name__)


class FactValidator:
    """Validates facts extracted by LLM against the actual database content."""

    def __init__(self, db_session: Session):
        """Initialize validator with database session.

        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session

    def extract_post_references(self, text: str) -> List[int]:
        """Extract post IDs from [post:123] references in text.

        Args:
            text: Text containing post references

        Returns:
            List of extracted post IDs
        """
        pattern = r'\[post:(\d+)\]'
        matches = re.findall(pattern, text)
        return [int(match) for match in matches]

    def validate_post_exists(self, post_id: int) -> bool:
        """Check if a post with given ID exists in database.

        Args:
            post_id: Telegram message ID to check

        Returns:
            True if post exists, False otherwise
        """
        post = self.db.query(Post).filter_by(telegram_message_id=post_id).first()
        return post is not None

    def validate_post_content(self, post_id: int, claimed_content: str) -> Tuple[bool, Optional[str]]:
        """Validate if claimed content matches actual post.

        Args:
            post_id: Telegram message ID
            claimed_content: Content claimed to be in the post

        Returns:
            Tuple of (is_valid, actual_content)
        """
        post = self.db.query(Post).filter_by(telegram_message_id=post_id).first()

        if not post:
            return False, None

        actual_content = post.message_text or ""

        # Normalize for comparison
        claimed_normalized = claimed_content.lower().strip()
        actual_normalized = actual_content.lower().strip()

        # Check if claimed content is a substring or very similar
        is_valid = claimed_normalized in actual_normalized or \
                   self._fuzzy_match(claimed_normalized, actual_normalized)

        return is_valid, actual_content

    def validate_dates(self, post_ids: List[int], claimed_period: Optional[str] = None) -> Dict[str, any]:
        """Validate dates for given posts.

        Args:
            post_ids: List of telegram message IDs
            claimed_period: Optional claimed time period (e.g., "последние 2 месяца")

        Returns:
            Dictionary with validation results
        """
        posts = self.db.query(Post).filter(
            Post.telegram_message_id.in_(post_ids)
        ).all()

        if not posts:
            return {"valid": False, "error": "No posts found"}

        dates = [post.created_at for post in posts]
        min_date = min(dates)
        max_date = max(dates)

        result = {
            "valid": True,
            "actual_period": {
                "start": min_date.strftime("%Y-%m-%d"),
                "end": max_date.strftime("%Y-%m-%d"),
                "months": self._get_month_names(dates)
            },
            "post_count": len(posts)
        }

        # Validate claimed period if provided
        if claimed_period:
            result["claimed_period"] = claimed_period
            result["period_match"] = self._validate_period_claim(
                claimed_period, min_date, max_date
            )

        return result

    def validate_links(self, post_id: int) -> Dict[str, any]:
        """Validate links and references for a post.

        Args:
            post_id: Telegram message ID

        Returns:
            Dictionary with link validation results
        """
        # Get links from this post
        outgoing = self.db.query(Link).filter_by(from_post_id=post_id).all()
        incoming = self.db.query(Link).filter_by(to_post_id=post_id).all()

        return {
            "post_id": post_id,
            "outgoing_links": [
                {
                    "to_post": link.to_post_id,
                    "type": link.link_type.value
                }
                for link in outgoing
            ],
            "incoming_links": [
                {
                    "from_post": link.from_post_id,
                    "type": link.link_type.value
                }
                for link in incoming
            ],
            "total_connections": len(outgoing) + len(incoming)
        }

    def generate_validation_report(self, answer: str, post_ids: List[int]) -> Dict[str, any]:
        """Generate comprehensive validation report for an answer.

        Args:
            answer: The answer text to validate
            post_ids: List of main source post IDs

        Returns:
            Validation report dictionary
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "validations": []
        }

        # Extract and validate post references
        referenced_posts = self.extract_post_references(answer)

        for post_id in referenced_posts:
            validation = {
                "post_id": post_id,
                "exists": self.validate_post_exists(post_id)
            }

            if validation["exists"]:
                # Get actual post content for fact checking
                post = self.db.query(Post).filter_by(
                    telegram_message_id=post_id
                ).first()

                validation["actual_date"] = post.created_at.strftime("%Y-%m-%d")
                validation["actual_month"] = self._get_month_name_ru(post.created_at)

            report["validations"].append(validation)

        # Validate main sources
        report["main_sources_validation"] = {
            "all_exist": all(self.validate_post_exists(pid) for pid in post_ids),
            "date_range": self.validate_dates(post_ids) if post_ids else None
        }

        # Calculate accuracy score
        total_refs = len(referenced_posts)
        valid_refs = sum(1 for v in report["validations"] if v["exists"])
        report["accuracy_score"] = valid_refs / total_refs if total_refs > 0 else 1.0

        return report

    def _fuzzy_match(self, text1: str, text2: str, threshold: float = 0.8) -> bool:
        """Simple fuzzy matching for content validation.

        Args:
            text1: First text
            text2: Second text
            threshold: Similarity threshold (0-1)

        Returns:
            True if texts are similar enough
        """
        # Simple implementation - can be enhanced with proper fuzzy matching
        words1 = set(text1.split())
        words2 = set(text2.split())

        if not words1 or not words2:
            return False

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        jaccard_similarity = len(intersection) / len(union)
        return jaccard_similarity >= threshold

    def _get_month_names(self, dates: List[datetime]) -> List[str]:
        """Get unique month names from dates in Russian.

        Args:
            dates: List of datetime objects

        Returns:
            List of unique month names
        """
        months = set()
        for date in dates:
            months.add(self._get_month_name_ru(date))
        return sorted(list(months))

    def _get_month_name_ru(self, date: datetime) -> str:
        """Get Russian month name from date.

        Args:
            date: Datetime object

        Returns:
            Russian month name
        """
        month_names = {
            1: "январь", 2: "февраль", 3: "март",
            4: "апрель", 5: "май", 6: "июнь",
            7: "июль", 8: "август", 9: "сентябрь",
            10: "октябрь", 11: "ноябрь", 12: "декабрь"
        }
        return f"{month_names.get(date.month, 'unknown')} {date.year}"

    def _validate_period_claim(self, claimed: str, start: datetime, end: datetime) -> bool:
        """Validate if claimed period matches actual dates.

        Args:
            claimed: Claimed period string
            start: Actual start date
            end: Actual end date

        Returns:
            True if claim is valid
        """
        # Simple validation - can be enhanced
        claimed_lower = claimed.lower()

        # Check for specific month mentions
        if "сентябр" in claimed_lower:
            return any(d.month == 9 for d in [start, end])
        if "август" in claimed_lower:
            return any(d.month == 8 for d in [start, end])
        if "июл" in claimed_lower:
            return any(d.month == 7 for d in [start, end])

        # Check for "последние X месяцев"
        if "последн" in claimed_lower and "месяц" in claimed_lower:
            # Extract number
            import re
            numbers = re.findall(r'\d+', claimed)
            if numbers:
                months_claimed = int(numbers[0])
                actual_months = (end.year - start.year) * 12 + end.month - start.month + 1
                return abs(actual_months - months_claimed) <= 1

        return True  # Default to valid if can't parse