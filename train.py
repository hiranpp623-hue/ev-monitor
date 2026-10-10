"""
train.py
--------
Trains an LSTM binary classifier: given a window of post-incident sensor
readings, predict whether the battery is stabilizing safely (0) or headed
toward reignition (1).
"""

import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.utils.class_weight import compute_class_weight

import tensorflow as tf
from tensorflow.keras import layers, models, callbacks

SEED = 7
tf.random.set_seed(SEED)


def load_data():
    X = np.load("sequences.npy")
    y = np.load("labels.npy")
    return X, y


def normalize(X_train, X_val, X_test):
    mean = X_train.reshape(-1, X_train.shape[-1]).mean(axis=0)
    std = X_train.reshape(-1, X_train.shape[-1]).std(axis=0) + 1e-8
    np.save("norm_mean.npy", mean)
    np.save("norm_std.npy", std)
    return (X_train - mean) / std, (X_val - mean) / std, (X_test - mean) / std


def build_model(timesteps, n_features):
    model = models.Sequential([
        layers.Input(shape=(timesteps, n_features)),
        layers.LSTM(48, return_sequences=True),
        layers.Dropout(0.3),
        layers.LSTM(24),
        layers.Dropout(0.3),
        layers.Dense(16, activation="relu"),
        layers.Dense(1, activation="sigmoid"),
    ])
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss="binary_crossentropy",
        metrics=["accuracy"],
    )
    return model


def estimate_early_warning(model, X_risk_raw, X_risk_norm, threshold=0.5):
    """How many timesteps EARLY does the model flag risk before the raw
    temperature re-spike (>5C rise from its local minimum) is obvious?
    Batched per-sequence for speed -- one predict() call per sequence
    instead of one per timestep."""
    leads = []
    for raw_seq, norm_seq in zip(X_risk_raw, X_risk_norm):
        temp1 = raw_seq[:, 0]
        min_idx = np.argmin(temp1)
        respike_idx = None
        for i in range(min_idx, len(temp1)):
            if temp1[i] - temp1[min_idx] > 5:
                respike_idx = i
                break
        if respike_idx is None:
            continue

        T = len(norm_seq)
        # build ALL padded windows for this sequence at once: shape (T-5, T, F)
        windows = []
        for t in range(5, T):
            w = norm_seq[:t].copy()
            pad_len = T - t
            if pad_len > 0:
                pad = np.repeat(w[-1:, :], pad_len, axis=0)
                w = np.concatenate([w, pad], axis=0)
            windows.append(w)
        windows = np.stack(windows, axis=0)   # (T-5, T, F)

        scores = model.predict(windows, verbose=0).flatten()   # ONE call
        crossed = np.where(scores >= threshold)[0]
        if len(crossed) > 0:
            detected_idx = crossed[0] + 5   # offset back to real timestep
            leads.append(respike_idx - detected_idx)

    if leads:
        print(f"\nEarly-warning analysis (n={len(leads)} reignition sequences):")
        print(f"  Mean early-warning lead: {np.mean(leads):.1f} timesteps")
    else:
        print("\nCould not compute early-warning lead (no valid sequences).")               



def main():
    X, y = load_data()

    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.30, stratify=y, random_state=SEED
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.50, stratify=y_temp, random_state=SEED
    )

    X_train_n, X_val_n, X_test_n = normalize(X_train, X_val, X_test)

    class_weights = compute_class_weight(
        class_weight="balanced", classes=np.unique(y_train), y=y_train
    )
    class_weight_dict = dict(enumerate(class_weights))

    model = build_model(X.shape[1], X.shape[2])
    model.summary()

    early_stop = callbacks.EarlyStopping(
        monitor="val_loss", patience=8, restore_best_weights=True
    )

    model.fit(
        X_train_n, y_train,
        validation_data=(X_val_n, y_val),
        epochs=60,
        batch_size=32,
        class_weight=class_weight_dict,
        callbacks=[early_stop],
        verbose=2,
    )

    y_pred_probs = model.predict(X_test_n, verbose=0).flatten()
    y_pred = (y_pred_probs >= 0.5).astype(int)

    print("\n=== Classification Report (test set) ===")
    print(classification_report(
        y_test, y_pred, target_names=["stabilizing", "reignition_risk"]
    ))

    print("=== Confusion Matrix ===")
    print(confusion_matrix(y_test, y_pred))

    risk_mask = y_test == 1
    estimate_early_warning(model, X_test[risk_mask], X_test_n[risk_mask])

    model.save("reignition_lstm.keras")
    print("\nSaved model to reignition_lstm.keras")


if __name__ == "__main__":
    main()