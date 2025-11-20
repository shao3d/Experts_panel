#!/bin/bash
# Validation script for expert migration
# Purpose: Verify expert_metadata consistency

DB="data/experts.db"

echo "🔍 Validating expert migration..."
echo ""

# Check 1: Posts with expert_id have channel_username
echo "Check 1: Posts with expert_id should have channel_username"
MISSING=$(sqlite3 $DB "SELECT COUNT(*) FROM posts WHERE expert_id IS NOT NULL AND channel_username IS NULL;")
if [ "$MISSING" -gt 0 ]; then
    echo "❌ FAILED: $MISSING posts missing channel_username"
    exit 1
else
    echo "✅ PASSED: All posts have channel_username"
fi

echo ""

# Check 2: All expert_id in posts exist in expert_metadata
echo "Check 2: All expert_id in posts should exist in expert_metadata"
ORPHANED=$(sqlite3 $DB "SELECT COUNT(DISTINCT p.expert_id) FROM posts p WHERE p.expert_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM expert_metadata em WHERE em.expert_id = p.expert_id);")
if [ "$ORPHANED" -gt 0 ]; then
    echo "❌ FAILED: Orphaned expert_ids found"
    exit 1
else
    echo "✅ PASSED: No orphaned expert_ids"
fi

echo ""

# Check 3: All experts in metadata have posts
echo "Check 3: All experts in metadata should have posts (warning only)"
NO_POSTS=$(sqlite3 $DB "SELECT GROUP_CONCAT(em.expert_id) FROM expert_metadata em WHERE NOT EXISTS (SELECT 1 FROM posts p WHERE p.expert_id = em.expert_id);")
if [ -n "$NO_POSTS" ]; then
    echo "⚠️  WARNING: Experts without posts: $NO_POSTS"
else
    echo "✅ PASSED: All experts have posts"
fi

echo ""
echo "✅ All validation checks passed!"
