# SSE Integration Testing Guide

## Prerequisites

1. **Set OpenAI API Key**:
   ```bash
   # Edit backend/.env and add your OpenAI API key
   # Replace 'your_openai_api_key_here' with actual key
   ```

2. **Install Dependencies**:
   ```bash
   # Backend
   cd backend
   pip install -r requirements.txt
   cd ..

   # Frontend
   cd frontend
   npm install
   cd ..
   ```

3. **Ensure Database Exists**:
   ```bash
   # Check that data/experts.db exists
   ls -la data/experts.db
   ```

## Testing Options

### Option 1: Manual Test with UI (Recommended)

Run the shell script that starts both servers:

```bash
./test_sse_integration.sh
```

Then:
1. Open http://localhost:5173 in browser
2. Enter a test query
3. Watch real-time SSE updates
4. Verify all phases complete
5. Press Ctrl+C to stop

### Option 2: Automated Test (No UI)

Start backend first:
```bash
cd backend
uvicorn src.api.main:app --reload --port 8000
```

In another terminal, run the test:
```bash
python test_sse_automated.py
```

This will:
- Connect to SSE endpoint
- Send test query
- Validate all phases complete
- Check result structure
- Report PASS/FAIL

### Option 3: Manual cURL Test

Test SSE stream directly:
```bash
curl -N "http://localhost:8000/api/v1/query/stream?query=test"
```

## Expected SSE Event Flow

1. **Map Phase**:
   ```json
   {"type": "phase_start", "phase": "map", "message": "..."}
   {"type": "map_progress", "chunk": 1, "total": 5, "posts_in_chunk": 20}
   {"type": "map_progress", "chunk": 2, "total": 5, "posts_in_chunk": 20}
   {"type": "phase_complete", "phase": "map"}
   ```

2. **Resolve Phase**:
   ```json
   {"type": "phase_start", "phase": "resolve", "message": "..."}
   {"type": "phase_complete", "phase": "resolve", "message": "Found X links"}
   ```

3. **Reduce Phase**:
   ```json
   {"type": "phase_start", "phase": "reduce", "message": "..."}
   {"type": "phase_complete", "phase": "reduce"}
   ```

4. **Final Result**:
   ```json
   {"type": "result", "result": {...}}
   ```

## Common Issues

### Backend Won't Start
- Check Python version (3.11+ required)
- Verify all dependencies installed
- Check port 8000 not in use

### No SSE Events
- Verify OPENAI_API_KEY is set correctly
- Check backend logs for errors
- Ensure database has data

### Frontend Connection Issues
- Check CORS settings in backend
- Verify frontend proxy config
- Check browser console for errors

## Success Criteria

✅ All three phases complete
✅ Progress events show chunk updates
✅ Final result contains answer and sources
✅ No errors in console
✅ UI updates in real-time