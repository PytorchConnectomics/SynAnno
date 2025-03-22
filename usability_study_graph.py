from textwrap import wrap

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.gridspec import GridSpec

# Define colors for response categories
colors = {
    "Strongly Disagree": "#5e2b74",
    "Disagree": "#c39bc6",
    "Neutral": "#6f6f6f",
    "Agree": "#9ccb9c",
    "Strongly Agree": "#008037",
}


# Load data from CSV file
def load_survey_data(file_path):
    df = pd.read_csv(file_path)
    df = df.drop(columns=["Timestamp"])  # Remove timestamp column

    # Count occurrences of each response category per question
    response_categories = [
        "Strongly Agree",
        "Agree",
        "Neutral",
        "Disagree",
        "Strongly Disagree",
    ]
    df_counts = pd.DataFrame()
    df_counts["Question"] = df.columns  # Questions as labels

    for category in response_categories:
        df_counts[category] = df.apply(
            lambda x: (x == category).sum(), axis=0  # noqa: B023
        ).values

    return df_counts


# Read survey data
df = load_survey_data("/Users/lando/Code/SynAnno/SynAnno_Useability_Study.csv")

# Compute agreement percentage
agreement_percentage = (
    (df["Strongly Agree"] + df["Agree"]) / df.iloc[:, 1:].sum(axis=1) * 100
).astype(int)

# Sort by agreement percentage (ascending), then by Strongly Agree count (ascending)
df["Agreement Percentage"] = agreement_percentage
df = df.sort_values(
    by=["Agreement Percentage", "Strongly Agree"], ascending=[True, True]
)

number_of_questions = len(df)
# Update questions to include Q<number>: prefix
wrapped_questions = [
    "\n".join(wrap(f"Q{number_of_questions-i}: {q.strip()}", 49))
    for i, q in enumerate(df["Question"])
]
df["Wrapped Question"] = wrapped_questions

# Normalize data to percentages
df_percentage = df.copy()
for col in df.columns[
    1:-2
]:  # Exclude Agreement Percentage and Wrapped Question from normalization
    df_percentage[col] = df[col] / df.iloc[:, 1:-2].sum(axis=1) * 100

# Compute left positions to center Neutral at zero
left_positions = -(
    df_percentage["Disagree"]
    + df_percentage["Strongly Disagree"]
    + df_percentage["Neutral"] / 2
)

# Create two-column layout using GridSpec
fig = plt.figure(figsize=(10, 8))
gs = GridSpec(1, 2, width_ratios=[3, 5], wspace=0.3)

# Text column
ax_text = fig.add_subplot(gs[0])
ax_text.set_xlim(0, 1)
ax_text.set_ylim(-0.5, len(df) - 0.5)
ax_text.axis("off")
for i, question in enumerate(df["Wrapped Question"]):
    ax_text.text(0, i, question, va="center", ha="left", fontsize=10)

# Bar chart column
ax_bar = fig.add_subplot(gs[1])
for category in ["Strongly Disagree", "Disagree", "Neutral", "Agree", "Strongly Agree"]:
    values = df_percentage[category].values
    ax_bar.barh(
        np.arange(len(df)),
        values,
        left=left_positions,
        color=colors[category],
        label=category,
        height=0.4,
    )
    left_positions += values

# Central axis
ax_bar.axvline(x=0, color="black", linewidth=1)

# Hide axes and ticks
ax_bar.set_yticks([])
ax_bar.set_yticklabels([])
ax_bar.set_xticks([])
ax_bar.set_xticklabels([])
ax_bar.spines["top"].set_visible(False)
ax_bar.spines["bottom"].set_visible(False)
ax_bar.spines["right"].set_visible(False)
ax_bar.spines["left"].set_visible(False)

# Add percentage labels to the right of the bars
for i, percentage in enumerate(df["Agreement Percentage"].values):
    ax_bar.text(105, i, f"{percentage}%", va="center", fontsize=10)

# Add legend below the chart
ax_bar.legend(loc="upper center", bbox_to_anchor=(0.1, 0.0), ncol=5, frameon=False)

ax_bar.set_xlim(-40, 120)
plt.tight_layout()
plt.show()
