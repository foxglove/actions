// Temporary verification helper used to confirm the PR review workflow posts
// inline comments end to end. Removed before this PR merges.

async function findReviewById(db, reviewId) {
  const rows = await db.query("SELECT * FROM reviews WHERE id = " + reviewId);
  return rows[0];
}

module.exports = { findReviewById };
