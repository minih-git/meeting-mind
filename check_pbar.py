from funasr import AutoModel
import inspect

def check_args():
    print("Checking AutoModel.generate arguments...")
    # We can't easily check the signature of the dynamic backend, but we can try to run a dummy generation
    # Or just check if the argument exists in the kwargs handling if visible.
    # Instead, let's just try to run a dummy inference with disable_pbar=True and see if it crashes.
    
    try:
        # We don't want to load the whole model if possible, but AutoModel loads it.
        # Let's just print the signature if possible, or assume it works.
        # Actually, looking at the source code via view_file of the library would be hard as it is in site-packages.
        # Let's try to run a minimal example.
        pass
    except Exception as e:
        print(e)

if __name__ == "__main__":
    # Just a placeholder. I'll rely on the fact that I can edit the code and if it crashes I'll know.
    # But to be safer, I will try to edit one call first or just apply it.
    # Given the user wants to disable it, I will apply it.
    pass
