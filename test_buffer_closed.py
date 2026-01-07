"""Test to reproduce the buffer closed issue"""
from poorwsgi.response import Response


def start_response(status_code, headers):
    """Mock start_response function"""
    print(f"Status: {status_code}")
    print(f"Headers: {headers}")
    return lambda data: None


def test_buffer_closed_after_iteration():
    """Test that buffer gets closed after WSGI server iterates over it"""
    res = Response("Hello World")
    
    # Simulate what WSGI server does
    result = res(start_response)
    
    # Iterate over the result (this is what WSGI server does)
    for chunk in result:
        print(f"Chunk: {chunk}")
    
    # Close the result (WSGI server closes it after iteration)
    if hasattr(result, 'close'):
        result.close()
    
    # Now try to access the data property - this should fail
    try:
        print(f"Data: {res.data}")
        print("ERROR: Should have raised ValueError!")
    except ValueError as e:
        print(f"SUCCESS: Got expected error: {e}")


def test_buffer_seek_in_end_of_response():
    """Test that seeks on closed buffer fail"""
    res = Response("Hello World")
    
    # Call response once
    result = res(start_response)
    
    # Close the buffer manually (simulating what WSGI server does)
    if hasattr(result, 'close'):
        result.close()
    
    # Try to call __end_of_response__ again or access data
    # This simulates the error in the stack trace
    try:
        data = res.data  # This calls seek(0)
        print(f"ERROR: Should have raised ValueError! Got: {data}")
    except ValueError as e:
        print(f"SUCCESS: Got expected error: {e}")


if __name__ == "__main__":
    print("Test 1: Buffer closed after iteration")
    test_buffer_closed_after_iteration()
    print("\nTest 2: Buffer seek in end_of_response")
    test_buffer_seek_in_end_of_response()
