import numpy as np
import os
from numpy.testing import assert_allclose, assert_almost_equal
from vw_executor.vw import ExecutionStatus
import vowpalwabbit as vw
from test_helper import get_function_object


def remove_non_digits(string):
    return "".join(char for char in string if char.isdigit() or char == ".")


def get_from_kwargs(kwargs, key, default=None):
    if key in kwargs:
        return kwargs[key]
    else:
        return default


def majority_close(arr1, arr2, rtol, atol, threshold):
    # Check if the majority of elements are close
    close_count = np.count_nonzero(np.isclose(arr1, arr2, rtol=rtol, atol=atol))
    return close_count >= len(arr1) * threshold


def assert_weight(job, **kwargs):
    atol = get_from_kwargs(kwargs, "atol", 10e-8)
    rtol = get_from_kwargs(kwargs, "rtol", 10e-5)
    expected_weights = kwargs["expected_weights"]
    assert job.status == ExecutionStatus.Success, f"{job.opts} job should be successful"
    data = job.outputs["--readable_model"]
    with open(data[0], "r") as f:
        data = f.readlines()
    data = [i.strip() for i in data]
    weights = job[0].model9("--readable_model").weights
    weights = weights["weight"].to_list()
    assert_allclose(
        weights, expected_weights, atol=atol, rtol=rtol
    ), f"weights should be {expected_weights}"


def assert_prediction(job, **kwargs):
    assert job.status == ExecutionStatus.Success, "job should be successful"
    atol = kwargs.get("atol", 10e-8)
    rtol = kwargs.get("rtol", 10e-5)
    threshold = kwargs.get("threshold", 0.9)
    expected_value = kwargs["expected_value"]
    predictions = job.outputs["-p"]
    with open(predictions[0], "r") as f:
        prediction = [i.strip() for i in f.readlines()]
        prediction = [i for i in prediction if i != ""]
        if ":" in prediction[0]:
            prediction = [[j.split(":")[1] for j in i.split(",")] for i in prediction]
        elif "," in prediction[0]:
            prediction = [[j for j in i.split(",")] for i in prediction]
        if type(prediction[0]) == list:
            prediction = [[float(remove_non_digits(j)) for j in i] for i in prediction]
        else:
            prediction = [float(remove_non_digits(i)) for i in prediction]
        assert majority_close(
            prediction,
            [expected_value] * len(prediction),
            rtol=rtol,
            atol=atol,
            threshold=threshold,
        ), f"predicted value should be {expected_value}, \n actual values are {prediction}"


def assert_loss(job, **kwargs):
    assert job.status == ExecutionStatus.Success, "job should be successful"
    assert type(job[0].loss) == float, "loss should be an float"
    decimal = kwargs.get("decimal", 2)
    assert_almost_equal(job[0].loss, kwargs["expected_loss"], decimal=decimal)


def assert_loss_below(job, **kwargs):
    assert job.status == ExecutionStatus.Success, "job should be successful"
    assert type(job[0].loss) == float, "loss should be an float"
    assert (
        job[0].loss <= kwargs["expected_loss"]
    ), f"loss should be below {kwargs['expected_loss']}"


def assert_prediction_with_generated_data(job, **kwargs):
    assert job.status == ExecutionStatus.Success, "job should be successful"
    expected_class = []
    trained_model = vw.Workspace(f"-i {job[0].model9('-f').path} --quiet")
    predictions = []
    folder_path = os.path.dirname(os.path.realpath(__file__))
    subdirectories = [
        os.path.join(folder_path, name)
        for name in os.listdir(folder_path)
        if os.path.isdir(os.path.join(folder_path, name))
    ]
    for subdir in subdirectories:
        try:
            subdir_name = subdir.replace("\\", "/").split("/")[-1]
            data_func_obj = get_function_object(
                f"{subdir_name}.data_generation", kwargs["data_func"]["name"]
            )
            if data_func_obj:
                break
        except:
            pass
    dataFile = data_func_obj(*kwargs["data_func"]["params"].values())
    with open(dataFile, "r") as f:
        for line in f.readlines():
            expected_class.append(line.split("|")[0].strip())
            predicted_class = trained_model.predict(line.strip())
            predictions.append(predicted_class)
    accuracy = sum(
        [1 if int(yp) == int(ye) else 0 for yp, ye in zip(predictions, expected_class)]
    ) / len(expected_class)
    assert (
        accuracy >= kwargs["accuracy_threshold"]
    ), f"Accuracy is {accuracy} and Threshold is {kwargs['accuracy_threshold']}"
