## App.build Experiment Hub 🧪
This repository is dedicated to **evaluating and experimenting** with the [app.build agent](https://github.com/appdotbuild/agent), an open-source AI agent built by Databricks that generates **production-ready full-stack applications from a single prompt**.

Our goal is to ensure the agent consistently delivers reliable, high-quality, and deployable applications.

---

### Important files:

#### 1. Logs:
- they live inside `data/logs` folder.

#### 2. Log extraction code:
- Important to extract code out of log files.
- It lives in the root directory with the name `code.ipynb`.
- Behind the scene it uses another python script that has all the underlying code for extracting information out of log files.
- This underlying python script is named as `extrac_log_data.py`.

#### 3. Evaluation results:
- They live inside [`data/evaluations.csv`](data/evaluations.csv).



---

*Explore the future of app development with app.build!*
