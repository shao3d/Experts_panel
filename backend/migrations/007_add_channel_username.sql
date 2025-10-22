-- Add channel_username column to posts table
-- This field is used for Telegram links and API responses

ALTER TABLE posts ADD COLUMN channel_username VARCHAR(255);

-- Create index for faster lookups
CREATE INDEX idx_posts_channel_username ON posts(channel_username);

-- Add comment explaining the purpose
COMMENT ON COLUMN posts.channel_username IS 'Telegram channel username for generating links';