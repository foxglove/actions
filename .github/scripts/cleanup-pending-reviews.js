// Pending reviews can be deleted only by the user that created them.
// The workflow calls this with the beefcake App token. A failed delete is
// retried with the workflow token so an older pending review is still attempted.
const OWN_PENDING_REVIEW_LOGINS = new Set(["foxglove-beefcake[bot]", "claude[bot]"]);

async function deleteWithWorkflowToken(context, reviewId) {
  const token = process.env.GITHUB_TOKEN;
  if (!token) {
    throw new Error("GITHUB_TOKEN is empty");
  }

  const owner = context.repo.owner;
  const repo = context.repo.repo;
  const pullNumber = context.payload.pull_request.number;
  const response = await fetch(
    `https://api.github.com/repos/${owner}/${repo}/pulls/${pullNumber}/reviews/${reviewId}`,
    {
      method: "DELETE",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${token}`,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "foxglove-actions-review-cleanup",
      },
    },
  );
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${response.status} ${body.slice(0, 300)}`);
  }
}

module.exports = async ({ github, context, core }) => {
  const reviews = await github.paginate(github.rest.pulls.listReviews, {
    owner: context.repo.owner,
    repo: context.repo.repo,
    pull_number: context.payload.pull_request.number,
    per_page: 100,
  });

  for (const review of reviews) {
    const reviewerLogin = review.user?.login;
    if (!OWN_PENDING_REVIEW_LOGINS.has(reviewerLogin) || review.state !== "PENDING") {
      continue;
    }

    try {
      await github.rest.pulls.deletePendingReview({
        owner: context.repo.owner,
        repo: context.repo.repo,
        pull_number: context.payload.pull_request.number,
        review_id: review.id,
      });
      core.info(`Deleted pending review ${review.id} from ${reviewerLogin}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      try {
        await deleteWithWorkflowToken(context, review.id);
        core.info(
          `Deleted pending review ${review.id} from ${reviewerLogin} with the workflow token`,
        );
      } catch (retryError) {
        const retryMessage = retryError instanceof Error ? retryError.message : String(retryError);
        core.warning(
          `Failed to delete pending review ${review.id} from ${reviewerLogin}: ${message}; workflow token retry: ${retryMessage}`,
        );
      }
    }
  }
};
