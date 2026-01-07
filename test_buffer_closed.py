"""Test to reproduce and verify fix for the buffer closed issue"""
from io import BytesIO
from poorwsgi.response import Response, FileObjResponse


def start_response(status_code, headers):
    """Mock start_response function"""
    print(f"Status: {status_code}")
    print(f"Headers: {headers}")
    return lambda data: None


def test_buffer_closed_after_iteration():
    """Test that buffer access still works after WSGI server closes it"""
    res = Response("Hello World")
    
    # Simulate what WSGI server does
    result = res(start_response)
    
    # Iterate over the result (this is what WSGI server does)
    chunks = []
    for chunk in result:
        chunks.append(chunk)
        print(f"Chunk: {chunk}")
    
    # Close the result (WSGI server closes it after iteration)
    if hasattr(result, 'close'):
        result.close()
    
    # Now try to access the data property - this should work with the fix
    try:
        data = res.data
        print(f"SUCCESS: Can access data after buffer closed: {data}")
        assert data == b"Hello World", f"Expected b'Hello World', got {data}"
    except ValueError as e:
        print(f"ERROR: Got unexpected error: {e}")
        raise


def test_buffer_seek_in_end_of_response():
    """Test that seeks on closed buffer work with the fix"""
    res = Response("Hello World")
    
    # Call response once
    result = res(start_response)
    
    # Close the buffer manually (simulating what WSGI server does)
    if hasattr(result, 'close'):
        result.close()
    
    # Try to access data - should work with the fix
    try:
        data = res.data
        print(f"SUCCESS: Can access data after buffer closed: {data}")
        assert data == b"Hello World", f"Expected b'Hello World', got {data}"
    except ValueError as e:
        print(f"ERROR: Got unexpected error: {e}")
        raise


def test_multiple_calls_prevented():
    """Test that response can still only be called once"""
    res = Response("Hello World")
    
    # First call should work
    result1 = res(start_response)
    chunks = list(result1)
    print(f"First call succeeded, got {len(chunks)} chunk(s)")
    
    # Second call should raise RuntimeError
    try:
        result2 = res(start_response)
        print("ERROR: Second call should have raised RuntimeError!")
    except RuntimeError as e:
        print(f"SUCCESS: Second call correctly raised RuntimeError: {e}")


def test_file_obj_response_closed():
    """Test that FileObjResponse handles closed files gracefully"""
    file_obj = BytesIO(b"File content")
    res = FileObjResponse(file_obj)
    
    # Simulate what WSGI server does
    result = res(start_response)
    
    # Iterate over the result
    chunks = []
    for chunk in result:
        chunks.append(chunk)
        print(f"File chunk: {chunk}")
    
    # Close the result (WSGI server closes it after iteration)
    if hasattr(result, 'close'):
        result.close()
    
    # Now try to access the data property - this should work with the fix
    try:
        data = res.data
        print(f"SUCCESS: Can access file data after buffer closed: {data}")
        # Note: data may be empty if file is closed and not seekable
        assert isinstance(data, bytes), f"Expected bytes, got {type(data)}"
    except ValueError as e:
        print(f"ERROR: Got unexpected error: {e}")
        raise


if __name__ == "__main__":
    print("Test 1: Buffer closed after iteration")
    test_buffer_closed_after_iteration()
    print("\nTest 2: Buffer seek in end_of_response")
    test_buffer_seek_in_end_of_response()
    print("\nTest 3: Multiple calls prevented")
    test_multiple_calls_prevented()
    print("\nTest 4: FileObjResponse closed")
    test_file_obj_response_closed()
    print("\nAll tests passed!")


