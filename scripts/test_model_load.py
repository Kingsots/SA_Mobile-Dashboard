#!/usr/bin/env python3
import pickle
import sys

try:
    model_path = '/home/ubuntu/opticore-bot/data/models/model_current.pkl'
    print(f"Loading model from: {model_path}")
    
    with open(model_path, 'rb') as f:
        data = pickle.load(f)
    
    print(f"✅ Loaded successfully: {type(data)}")
    
    if isinstance(data, dict):
        print(f"Keys: {list(data.keys())}")
        if 'model' in data:
            model = data['model']
            print(f"Model type: {type(model)}")
            print(f"Model classes: {model.classes_}")
            print(f"Model n_estimators: {model.n_estimators}")
    else:
        print(f"Direct model: {type(data)}")
        print(f"Classes: {data.classes_}")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
