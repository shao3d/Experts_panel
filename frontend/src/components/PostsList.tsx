import React, { useState, useEffect, useRef } from 'react';
import PostCard from './PostCard';
import { PostDetailResponse } from '../types/api';

// Extend PostDetailResponse to include relevance_score from Map phase
interface PostWithRelevance extends PostDetailResponse {
  relevance_score?: 'HIGH' | 'MEDIUM' | 'LOW' | null;
}

interface PostsListProps {
  posts: PostWithRelevance[];
  selectedPostId?: number | null;
  expertId?: string;
}

const PostsList: React.FC<PostsListProps> = ({ posts, selectedPostId, expertId }) => {
  // Track which posts have expanded comments
  const [expandedPosts, setExpandedPosts] = useState<Set<number>>(new Set());
  const containerRef = useRef<HTMLDivElement>(null);

  // Scroll to selected post when it changes
  useEffect(() => {
    if (selectedPostId && containerRef.current) {
      // Try to find the post with expert prefix first
      let element = document.getElementById(`post-${expertId || 'unknown'}-${selectedPostId}`);

      // Fallback to old format for compatibility
      if (!element) {
        element = document.getElementById(`post-${selectedPostId}`);
      }

      if (element) {
        // Smooth scroll to the element
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });

        // Add temporary highlight animation
        element.style.transition = 'background-color 0.3s ease';
        const originalBg = element.style.backgroundColor;
        element.style.backgroundColor = '#fff3cd';
        setTimeout(() => {
          element.style.backgroundColor = originalBg;
        }, 2000);
      }
    }
  }, [selectedPostId]);

  const toggleComments = (postId: number) => {
    setExpandedPosts(prev => {
      const newSet = new Set(prev);
      if (newSet.has(postId)) {
        newSet.delete(postId);
      } else {
        newSet.add(postId);
      }
      return newSet;
    });
  };

  // Sort posts by relevance (HIGH -> MEDIUM -> LOW)
  const sortedPosts = [...posts].sort((a, b) => {
    const scoreOrder = { 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1, undefined: 0 };
    const scoreA = scoreOrder[a.relevance_score as keyof typeof scoreOrder] || 0;
    const scoreB = scoreOrder[b.relevance_score as keyof typeof scoreOrder] || 0;
    return scoreB - scoreA;
  });

  return (
    <div
      ref={containerRef}
      style={{
        padding: '0',
        backgroundColor: 'transparent',
      }}
    >
      {sortedPosts.map(post => (
        <PostCard
          key={post.telegram_message_id}
          post={post}
          isExpanded={expandedPosts.has(post.telegram_message_id)}
          onToggleComments={() => toggleComments(post.telegram_message_id)}
          isSelected={post.telegram_message_id === selectedPostId}
        />
      ))}

      {posts.length === 0 && (
        <div style={{
          textAlign: 'center',
          padding: '40px',
          color: '#6c757d',
          fontSize: '16px',
        }}>
          No posts loaded
        </div>
      )}
    </div>
  );
};

export default PostsList;