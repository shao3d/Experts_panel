#!/usr/bin/env python3
"""Interactive CLI tool for collecting expert comments on posts."""

import sys
import argparse
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

try:
    from rich.console import Console
    from rich.prompt import Prompt, Confirm, IntPrompt
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.markdown import Markdown
except ImportError:
    print("Error: 'rich' library is required for this tool.")
    print("Please install it: pip install rich")
    sys.exit(1)

from models import SessionLocal, Post, Comment
from sqlalchemy import func, or_


class CommentCollector:
    """Interactive CLI for collecting expert comments."""

    def __init__(self, expert_name: str = None):
        """Initialize the comment collector.

        Args:
            expert_name: Name of the expert adding comments
        """
        self.console = Console()
        self.db = SessionLocal()
        self.expert_name = expert_name
        self.session_stats = {
            'posts_viewed': 0,
            'comments_added': 0,
            'comments_edited': 0,
            'session_start': datetime.utcnow()
        }

    def run(self):
        """Run the interactive comment collection session."""
        self.console.clear()
        self._show_welcome()

        # Get expert name if not provided
        if not self.expert_name:
            self.expert_name = self._get_expert_name()

        # Main loop
        while True:
            action = self._show_main_menu()

            if action == "1":
                self._browse_posts()
            elif action == "2":
                self._search_posts()
            elif action == "3":
                self._review_comments()
            elif action == "4":
                self._show_statistics()
            elif action == "5":
                self._export_comments()
            elif action == "q":
                if self._confirm_exit():
                    break
            else:
                self.console.print("[red]Invalid option. Please try again.[/red]")

        self._show_goodbye()
        self.db.close()

    def _show_welcome(self):
        """Show welcome message."""
        welcome_text = """
        # 📝 Expert Comment Collector

        Welcome to the interactive comment collection tool!
        This tool helps you add contextual comments to posts from Telegram channels.

        Your comments will help enrich the dataset and improve answer quality.
        """
        self.console.print(Panel(Markdown(welcome_text), title="Welcome", border_style="green"))

    def _get_expert_name(self) -> str:
        """Get expert name from user."""
        name = Prompt.ask(
            "\n[bold cyan]Please enter your name[/bold cyan]",
            default="Anonymous Expert"
        )
        self.console.print(f"\n[green]Welcome, {name}![/green]\n")
        return name

    def _show_main_menu(self) -> str:
        """Show main menu and get user choice."""
        menu = Table(show_header=False, box=None)
        menu.add_column("Option", style="cyan", width=3)
        menu.add_column("Description")

        menu.add_row("1", "Browse posts chronologically")
        menu.add_row("2", "Search posts by keyword")
        menu.add_row("3", "Review your comments")
        menu.add_row("4", "Show session statistics")
        menu.add_row("5", "Export comments")
        menu.add_row("q", "Exit")

        self.console.print("\n[bold]Main Menu:[/bold]")
        self.console.print(menu)

        return Prompt.ask("\nYour choice", choices=["1", "2", "3", "4", "5", "q"])

    def _browse_posts(self):
        """Browse posts chronologically."""
        # Get total post count
        total_posts = self.db.query(func.count(Post.post_id)).scalar()

        if total_posts == 0:
            self.console.print("[yellow]No posts found in database.[/yellow]")
            return

        self.console.print(f"\n[cyan]Total posts in database: {total_posts}[/cyan]")

        # Ask for starting position
        start_from = IntPrompt.ask(
            "Start from post number",
            default=1,
            show_default=True
        )

        # Get posts
        offset = max(0, start_from - 1)
        posts = self.db.query(Post).order_by(Post.created_at).offset(offset).limit(100).all()

        # Navigate through posts
        current_index = 0
        while current_index < len(posts):
            post = posts[current_index]
            self._display_post(post, current_index + offset + 1, total_posts)

            # Check for existing comment
            existing_comment = self.db.query(Comment).filter(
                Comment.post_id == post.post_id,
                Comment.expert_name == self.expert_name
            ).first()

            if existing_comment:
                self.console.print(Panel(
                    f"[yellow]Your existing comment:[/yellow]\n{existing_comment.comment_text}",
                    border_style="yellow"
                ))

            # Show navigation options
            action = self._get_navigation_action(current_index, len(posts), bool(existing_comment))

            if action == "c":  # Add/edit comment
                self._add_comment(post, existing_comment)
            elif action == "n":  # Next
                current_index += 1
                self.session_stats['posts_viewed'] += 1
            elif action == "p":  # Previous
                if current_index > 0:
                    current_index -= 1
            elif action == "s":  # Skip to
                new_index = IntPrompt.ask(
                    f"Skip to post (1-{len(posts)})",
                    default=current_index + 1
                )
                current_index = max(0, min(new_index - 1, len(posts) - 1))
            elif action == "m":  # Main menu
                break

    def _search_posts(self):
        """Search posts by keyword."""
        keyword = Prompt.ask("\n[cyan]Enter search keyword[/cyan]")

        # Search in message text
        posts = self.db.query(Post).filter(
            Post.message_text.contains(keyword)
        ).order_by(Post.created_at).all()

        if not posts:
            self.console.print(f"[yellow]No posts found containing '{keyword}'[/yellow]")
            return

        self.console.print(f"\n[green]Found {len(posts)} posts containing '{keyword}'[/green]\n")

        # Navigate through search results
        current_index = 0
        while current_index < len(posts):
            post = posts[current_index]
            self._display_post(post, current_index + 1, len(posts))

            # Highlight keyword in text
            if post.message_text:
                highlighted = post.message_text.replace(
                    keyword,
                    f"[bold yellow]{keyword}[/bold yellow]"
                )
                self.console.print(Panel(highlighted, title="Content (highlighted)", border_style="yellow"))

            # Check for existing comment
            existing_comment = self.db.query(Comment).filter(
                Comment.post_id == post.post_id,
                Comment.expert_name == self.expert_name
            ).first()

            if existing_comment:
                self.console.print(Panel(
                    f"[yellow]Your existing comment:[/yellow]\n{existing_comment.comment_text}",
                    border_style="yellow"
                ))

            # Show navigation options
            action = self._get_navigation_action(current_index, len(posts), bool(existing_comment))

            if action == "c":  # Add/edit comment
                self._add_comment(post, existing_comment)
            elif action == "n":  # Next
                current_index += 1
                self.session_stats['posts_viewed'] += 1
            elif action == "p":  # Previous
                if current_index > 0:
                    current_index -= 1
            elif action == "m":  # Main menu
                break

    def _display_post(self, post: Post, current: int, total: int):
        """Display a single post."""
        self.console.clear()

        # Header
        header = Table(show_header=False, box=None)
        header.add_column("Field", style="cyan", width=20)
        header.add_column("Value")

        header.add_row("Post", f"{current}/{total}")
        header.add_row("ID", str(post.telegram_message_id))
        header.add_row("Channel", post.channel_name or "Unknown")
        header.add_row("Author", post.author_name or "Unknown")
        header.add_row("Date", post.created_at.strftime("%Y-%m-%d %H:%M") if post.created_at else "Unknown")
        header.add_row("Views", str(post.view_count))

        self.console.print(Panel(header, title="Post Information", border_style="blue"))

        # Content
        if post.message_text:
            # Truncate very long posts
            content = post.message_text
            if len(content) > 1000:
                content = content[:1000] + "...\n[dim](truncated)[/dim]"

            self.console.print(Panel(content, title="Content", border_style="green"))
        else:
            self.console.print(Panel("[dim]No text content (media only)[/dim]", title="Content"))

        # Media info
        if post.media_metadata:
            media_info = f"Type: {post.media_metadata.get('type', 'Unknown')}"
            if post.media_metadata.get('file_name'):
                media_info += f"\nFile: {post.media_metadata['file_name']}"
            self.console.print(Panel(media_info, title="Media", border_style="yellow"))

    def _get_navigation_action(self, current: int, total: int, has_comment: bool) -> str:
        """Get navigation action from user."""
        options = []

        if has_comment:
            options.append("[c] Edit comment")
        else:
            options.append("[c] Add comment")

        if current < total - 1:
            options.append("[n] Next")
        if current > 0:
            options.append("[p] Previous")

        options.extend([
            "[s] Skip to post",
            "[m] Main menu"
        ])

        self.console.print("\n" + " | ".join(options))

        valid_choices = ["c", "n", "p", "s", "m"]
        return Prompt.ask("Action", choices=[c for c in valid_choices if any(c in opt for opt in options)])

    def _add_comment(self, post: Post, existing_comment: Optional[Comment] = None):
        """Add or edit a comment for a post."""
        self.console.print("\n[bold cyan]Add your expert comment:[/bold cyan]")
        self.console.print("[dim]You can use markdown formatting. Enter 'DONE' on a new line to finish.[/dim]\n")

        # Multi-line input
        lines = []
        if existing_comment:
            self.console.print("[dim]Current comment (press Enter to keep, or type new comment):[/dim]")
            self.console.print(f"[yellow]{existing_comment.comment_text}[/yellow]\n")

        while True:
            line = input()
            if line == "DONE":
                break
            lines.append(line)

        comment_text = "\n".join(lines).strip()

        if not comment_text:
            if existing_comment:
                self.console.print("[yellow]Keeping existing comment[/yellow]")
                return
            else:
                self.console.print("[yellow]No comment added[/yellow]")
                return

        # Save comment
        try:
            if existing_comment:
                existing_comment.comment_text = comment_text
                existing_comment.created_at = datetime.utcnow()
                self.session_stats['comments_edited'] += 1
                self.console.print("[green]Comment updated successfully![/green]")
            else:
                new_comment = Comment(
                    post_id=post.post_id,
                    expert_name=self.expert_name,
                    comment_text=comment_text,
                    created_at=datetime.utcnow()
                )
                self.db.add(new_comment)
                self.session_stats['comments_added'] += 1
                self.console.print("[green]Comment added successfully![/green]")

            self.db.commit()

        except Exception as e:
            self.console.print(f"[red]Error saving comment: {e}[/red]")
            self.db.rollback()

        input("\nPress Enter to continue...")

    def _review_comments(self):
        """Review comments added by this expert."""
        comments = self.db.query(Comment).filter(
            Comment.expert_name == self.expert_name
        ).order_by(Comment.created_at.desc()).all()

        if not comments:
            self.console.print("[yellow]You haven't added any comments yet.[/yellow]")
            input("\nPress Enter to continue...")
            return

        self.console.clear()
        self.console.print(f"[bold]Your comments ({len(comments)} total):[/bold]\n")

        for i, comment in enumerate(comments, 1):
            post = self.db.query(Post).filter(Post.post_id == comment.post_id).first()

            if post:
                # Show post info
                info = f"Post ID: {post.telegram_message_id} | "
                info += f"Date: {post.created_at.strftime('%Y-%m-%d') if post.created_at else 'Unknown'}"
                self.console.print(f"[cyan]{i}. {info}[/cyan]")

                # Show post excerpt
                if post.message_text:
                    excerpt = post.message_text[:100] + "..." if len(post.message_text) > 100 else post.message_text
                    self.console.print(f"[dim]Post: {excerpt}[/dim]")

                # Show comment
                self.console.print(Panel(comment.comment_text, border_style="green"))
                self.console.print("")

        input("Press Enter to continue...")

    def _show_statistics(self):
        """Show session and overall statistics."""
        self.console.clear()

        # Session stats
        session_duration = (datetime.utcnow() - self.session_stats['session_start']).total_seconds() / 60

        session_table = Table(title="Session Statistics", show_header=False)
        session_table.add_column("Metric", style="cyan", width=30)
        session_table.add_column("Value", style="green")

        session_table.add_row("Expert Name", self.expert_name)
        session_table.add_row("Session Duration", f"{session_duration:.1f} minutes")
        session_table.add_row("Posts Viewed", str(self.session_stats['posts_viewed']))
        session_table.add_row("Comments Added", str(self.session_stats['comments_added']))
        session_table.add_row("Comments Edited", str(self.session_stats['comments_edited']))

        self.console.print(session_table)

        # Overall stats
        total_posts = self.db.query(func.count(Post.post_id)).scalar()
        total_comments = self.db.query(func.count(Comment.comment_id)).scalar()
        your_comments = self.db.query(func.count(Comment.comment_id)).filter(
            Comment.expert_name == self.expert_name
        ).scalar()
        commented_posts = self.db.query(func.count(func.distinct(Comment.post_id))).scalar()

        overall_table = Table(title="Overall Statistics", show_header=False)
        overall_table.add_column("Metric", style="cyan", width=30)
        overall_table.add_column("Value", style="green")

        overall_table.add_row("Total Posts", str(total_posts))
        overall_table.add_row("Total Comments", str(total_comments))
        overall_table.add_row("Your Comments", str(your_comments))
        overall_table.add_row("Posts with Comments", f"{commented_posts} ({commented_posts/total_posts*100:.1f}%)" if total_posts > 0 else "0")

        self.console.print("\n")
        self.console.print(overall_table)

        input("\nPress Enter to continue...")

    def _export_comments(self):
        """Export comments to JSON file."""
        filename = Prompt.ask(
            "\n[cyan]Export filename[/cyan]",
            default=f"comments_{self.expert_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.json"
        )

        try:
            import json

            comments = self.db.query(Comment).filter(
                Comment.expert_name == self.expert_name
            ).all()

            export_data = []
            for comment in comments:
                post = self.db.query(Post).filter(Post.post_id == comment.post_id).first()
                export_data.append({
                    'comment_id': comment.comment_id,
                    'post_telegram_id': post.telegram_message_id if post else None,
                    'post_text': post.message_text[:200] if post and post.message_text else None,
                    'comment_text': comment.comment_text,
                    'expert_name': comment.expert_name,
                    'created_at': comment.created_at.isoformat() if comment.created_at else None
                })

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

            self.console.print(f"[green]Successfully exported {len(export_data)} comments to {filename}[/green]")

        except Exception as e:
            self.console.print(f"[red]Error exporting comments: {e}[/red]")

        input("\nPress Enter to continue...")

    def _confirm_exit(self) -> bool:
        """Confirm exit and show session summary."""
        self.console.print("\n[bold]Session Summary:[/bold]")
        self.console.print(f"Comments added: {self.session_stats['comments_added']}")
        self.console.print(f"Comments edited: {self.session_stats['comments_edited']}")

        return Confirm.ask("\n[yellow]Are you sure you want to exit?[/yellow]")

    def _show_goodbye(self):
        """Show goodbye message."""
        self.console.print("\n[green]Thank you for your contributions![/green]")
        self.console.print(f"[cyan]Session ended at {datetime.now().strftime('%Y-%m-%d %H:%M')}[/cyan]\n")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Interactive tool for collecting expert comments on posts'
    )
    parser.add_argument(
        '--expert',
        help='Expert name (will be prompted if not provided)'
    )

    args = parser.parse_args()

    # Create and run collector
    collector = CommentCollector(expert_name=args.expert)

    try:
        collector.run()
    except KeyboardInterrupt:
        print("\n\nSession interrupted by user.")
        return 1
    except Exception as e:
        print(f"\nError: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())