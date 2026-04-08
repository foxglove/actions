module.exports = async ({ github, context, core }) => {
  const reviews = await github.paginate(github.rest.pulls.listReviews, {
    owner: context.repo.owner,
    repo: context.repo.repo,
    pull_number: context.payload.pull_request.number,
    per_page: 100,
  });

  for (const review of reviews) {
    const reviewerLogin = review.user?.login;
    if (reviewerLogin !== "claude[bot]" || review.state !== "PENDING") {
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
      core.warning(
        `Failed to delete pending review ${review.id} from ${reviewerLogin}: ${message}`,
      );
    }
  }
};
