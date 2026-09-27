"""Frozen multilingual MPNet embeddings with explicit cache and dataset provenance."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

MODEL = 'sentence-transformers/paraphrase-multilingual-mpnet-base-v2'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL, cache_folder='data/cache/huggingface', device='cpu')
    if args.smoke:
        vectors = model.encode(['Phát triển ứng dụng web.', 'Nghiên cứu học máy.'], normalize_embeddings=True)
        assert vectors.shape == (2, 768) and np.isfinite(vectors).all()
        print(json.dumps({'model': MODEL, 'shape': list(vectors.shape), 'finite': True}))
        return
    from .dataset import load_dataset
    data = load_dataset(allow_partial=args.allow_partial)
    output = Path('data/embeddings_smoke' if data['partial'] else 'data/embeddings')
    output.mkdir(parents=True, exist_ok=True)
    metadata = {'model': MODEL, 'dataset_sha256': data['sha256'], 'partial_data': data['partial'],
                'max_sequence_length': model.max_seq_length, 'normalization': 'L2', 'artifacts': {}}
    for filename, texts in [('thesis_embeddings', [row['feature_text'] for row in data['students']]),
                            ('advisor_embeddings', data['advisor_texts'])]:
        vectors = model.encode(texts, batch_size=16, normalize_embeddings=True, show_progress_bar=True)
        if vectors.shape != (len(texts), 768) or not np.isfinite(vectors).all():
            raise ValueError('Invalid embedding matrix')
        path = output / (filename + '.npy')
        np.save(path, vectors)
        metadata['artifacts'][path.name] = {'shape': list(vectors.shape),
                                          'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    (output / 'manifest.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    print(json.dumps(metadata))


if __name__ == '__main__':
    main()
