import torch
import numpy as np
from scipy.stats import pearsonr, spearmanr
from seqeval.metrics import f1_score as seq_f1_score
from sklearn.metrics import matthews_corrcoef, f1_score


def simple_accuracy(preds, labels):
    # TODO: THIS HACKY TRY CATCH IS FOR GNAD
    try:
        preds = np.array(preds)
        labels = np.array(labels)
        correct = preds == labels
        return {"acc": correct.mean()}
    except TypeError:
        return {"acc": (preds == labels.numpy()).mean()}


def acc_and_f1(preds, labels):
    acc = simple_accuracy(preds, labels)
    f1 = f1_score(y_true=labels, y_pred=preds)
    return {"acc": acc, "f1": f1, "acc_and_f1": (acc + f1) / 2}


def f1_macro(preds, labels):
    return {"f1_macro": f1_score(y_true=labels, y_pred=preds, average="macro")}


def pearson_and_spearman(preds, labels):
    pearson_corr = pearsonr(preds, labels)[0]
    spearman_corr = spearmanr(preds, labels)[0]
    return {
        "pearson": pearson_corr,
        "spearmanr": spearman_corr,
        "corr": (pearson_corr + spearman_corr) / 2,
    }


def compute_metrics(metric, preds, labels):
    assert len(preds) == len(labels)
    if metric == "mcc":
        return {"mcc": matthews_corrcoef(labels, preds)}
    elif metric == "acc":
        return simple_accuracy(preds, labels)
    elif metric == "acc_f1":
        return acc_and_f1(preds, labels)
    elif metric == "pear_spear":
        return pearson_and_spearman(preds, labels)
    # TODO this metric seems very specific for NER and doesnt work for
    elif metric == "seq_f1":
        return {"seq_f1": seq_f1_score(labels, preds)}
    elif metric == "postprocessed_seq_f1":
        return postprocessed_seq_f1_score(preds, labels)
    elif metric == "f1_macro":
        return f1_macro(preds, labels)
    elif metric == "squad":
        return squad(preds, labels)
    # elif metric == "masked_accuracy":
    #     return simple_accuracy(preds, labels, ignore=-1)
    else:
        raise KeyError(metric)


def _correct_bio_encodings(predictions):
    for sent_index in range(len(predictions)):
        label_started = False
        label_class = None

        for label_index in range(len(predictions[sent_index])):
            label = predictions[sent_index][label_index]
            if label.startswith("B-"):
                label_started = True
                label_class = label[2:]

            elif label == "O":
                label_started = False
                label_class = None
            elif label.startswith("I-"):
                if not label_started or label[2:] != label_class:
                    predictions[sent_index][label_index] = "O"
                    label_started = False
                    label_class = None
            else:
                assert False  # Should never be reached
    return predictions


def postprocessed_seq_f1_score(preds, labels):
    preds = [
        [token if token not in {"X", "[PAD]"} else "O" for token in sent]
        for sent in preds
    ]
    preds = _correct_bio_encodings(preds)
    f1_seq = seq_f1_score(labels, preds)
    return {"f1_seq_p": f1_seq}


def squad_EM(preds, labels):
    # scoring in tokenized space, so results to public leaderboard will vary
    pred_start = torch.cat(preds[::2])
    pred_end = torch.cat(preds[1::2])
    label_start = torch.cat(labels[::2])
    label_end = torch.cat(labels[1::2])
    assert len(label_start) == len(pred_start)
    num_total = len(label_start)
    num_correct = 0
    for i in range(num_total):
        if pred_start[i] == label_start[i] and pred_end[i] == label_end[i]:
            num_correct += 1
    return num_correct / num_total


def squad_f1(preds, labels):
    # scoring in tokenized space, so results to public leaderboard will vary
    pred_start = torch.cat(preds[::2]).cpu().numpy()
    pred_end = torch.cat(preds[1::2]).cpu().numpy()
    label_start = torch.cat(labels[::2]).cpu().numpy()
    label_end = torch.cat(labels[1::2]).cpu().numpy()
    assert len(label_start) == len(pred_start)
    num_total = len(label_start)
    f1_scores = []
    prec_scores = []
    recall_scores = []
    for i in range(num_total):
        if (pred_start[i] + pred_end[i]) <= 0 or (label_start[i] + label_end[i]) <= 0:
            # If either is no-answer, then F1 is 1 if they agree, 0 otherwise
            f1_scores.append(pred_end[i] == label_end[i])
            prec_scores.append(pred_end[i] == label_end[i])
            recall_scores.append(pred_end[i] == label_end[i])
        else:
            pred_range = set(range(pred_start[i], pred_end[i]))
            true_range = set(range(label_start[i], label_end[i]))
            num_same = len(true_range.intersection(pred_range))
            if num_same == 0:
                f1_scores.append(0)
                prec_scores.append(0)
                recall_scores.append(0)
            else:
                precision = 1.0 * num_same / len(pred_range)
                recall = 1.0 * num_same / len(true_range)
                f1 = (2 * precision * recall) / (precision + recall)
                f1_scores.append(f1)
                prec_scores.append(precision)
                recall_scores.append(recall)
    return (
        np.mean(np.array(prec_scores)),
        np.mean(np.array(recall_scores)),
        np.mean(np.array(f1_scores)),
    )


def squad(preds, labels):
    em = squad_EM(preds=preds, labels=labels)
    f1 = squad_f1(preds=preds, labels=labels)

    return {"EM": em, "f1": f1}
