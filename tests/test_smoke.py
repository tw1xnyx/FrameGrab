"""Legacy test entry point; use tests/test_pipeline.py for realistic FFprobe + FFmpeg smoke tests."""
if __name__ == '__main__':
    import os, runpy
    runpy.run_path(os.path.join(os.path.dirname(__file__), 'test_pipeline.py'), run_name='__main__')
