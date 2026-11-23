"""Framework-free matching and safe draw selection for Bunutan."""

from collections.abc import Iterable, Sequence
import secrets
from typing import Callable, Protocol


class DrawDeadlock(Exception):
    """Raised when no valid continuation remains for a draw."""


class RandomSource(Protocol):
    def choice(self, seq: Sequence[int]) -> int: ...
    def randrange(self, stop: int) -> int: ...


def allowed(giver_id: int, receiver_id: int, forbidden_pairs: set[tuple[int, int]]) -> bool:
    """Return whether a giver may take a receiver's slip."""
    return giver_id != receiver_id and (giver_id, receiver_id) not in forbidden_pairs


def has_perfect_matching(
    giver_ids: Sequence[int], receiver_ids: Sequence[int], forbidden_pairs: set[tuple[int, int]]
) -> bool:
    """Check whether all remaining givers can receive distinct allowed slips."""
    if len(giver_ids) != len(receiver_ids):
        return False
    if not giver_ids:
        return True

    matched_to = _maximum_matching(giver_ids, receiver_ids, forbidden_pairs)
    return len(matched_to) == len(giver_ids)


def _maximum_matching(
    giver_ids: Sequence[int], receiver_ids: Sequence[int], forbidden_pairs: set[tuple[int, int]]
) -> dict[int, int]:
    """Return a maximum receiver-to-giver matching using augmenting paths."""
    receivers = set(receiver_ids)
    ordered_givers = sorted(
        giver_ids,
        key=lambda giver: sum(allowed(giver, receiver, forbidden_pairs) for receiver in receivers),
    )
    matched_to: dict[int, int] = {}

    def augment(giver: int, seen: set[int]) -> bool:
        for receiver in receivers:
            if receiver in seen or not allowed(giver, receiver, forbidden_pairs):
                continue
            seen.add(receiver)
            if receiver not in matched_to or augment(matched_to[receiver], seen):
                matched_to[receiver] = giver
                return True
        return False

    for giver in ordered_givers:
        augment(giver, set())
    return matched_to


def _completion_counts(
    giver_ids: Sequence[int], receiver_ids: Sequence[int], forbidden_pairs: set[tuple[int, int]]
) -> tuple[dict[int, int], Callable[[int], int]]:
    """Build a shared bitmask DP for all possible first receiver choices."""
    receiver_ids = tuple(receiver_ids)
    giver_ids = tuple(giver_ids)
    receiver_index = {receiver: i for i, receiver in enumerate(receiver_ids)}
    allowed_masks = {
        giver: sum(1 << receiver_index[r] for r in receiver_ids if allowed(giver, r, forbidden_pairs))
        for giver in giver_ids
    }
    initial_size = len(giver_ids)
    cache = [-1] * (1 << len(receiver_ids))

    def count(mask: int) -> int:
        cached = cache[mask]
        if cached >= 0:
            return cached
        depth = initial_size - mask.bit_count()
        if depth == initial_size:
            cache[mask] = 1
            return 1
        giver = giver_ids[depth]
        choices = mask & allowed_masks[giver]
        total = 0
        while choices:
            bit = choices & -choices
            choices -= bit
            total += count(mask ^ bit)
        cache[mask] = total
        return total

    return receiver_index, count


def choose_receiver(
    giver_id: int,
    remaining_giver_ids: Iterable[int],
    remaining_receiver_ids: Iterable[int],
    forbidden_pairs: set[tuple[int, int]],
    rng: RandomSource | None = None,
    weight_completions: bool = True,
) -> int:
    """Choose a receiver without making the remaining full draw impossible.

    For up to 20 remaining names, candidates are weighted by the number of
    complete assignments they allow. Larger bowls use matching feasibility.
    """
    rng = rng or secrets.SystemRandom()
    givers = tuple(remaining_giver_ids)
    receivers = tuple(remaining_receiver_ids)
    if giver_id not in givers:
        raise DrawDeadlock("giver is not among the remaining givers")
    if len(givers) != len(receivers):
        raise DrawDeadlock("giver and receiver counts do not match")

    candidates = [receiver for receiver in receivers if allowed(giver_id, receiver, forbidden_pairs)]
    future_givers = tuple(giver for giver in givers if giver != giver_id)
    if not candidates:
        raise DrawDeadlock("no receiver is allowed for this giver")

    if len(givers) <= 20 and weight_completions:
        receiver_index, count = _completion_counts(future_givers, receivers, forbidden_pairs)
        all_mask = (1 << len(receivers)) - 1
        weights = [(receiver, count(all_mask ^ (1 << receiver_index[receiver]))) for receiver in candidates]
        weights = [(receiver, weight) for receiver, weight in weights if weight]
        total = sum(weight for _, weight in weights)
        if total == 0:
            raise DrawDeadlock("no candidate preserves a complete assignment")
        ticket = rng.randrange(total)
        for receiver, weight in weights:
            if ticket < weight:
                return receiver
            ticket -= weight
        raise DrawDeadlock("weighted draw selection failed")

    # A maximum matching of all future givers into the receiver set has one
    # unmatched receiver. Alternating paths identify every receiver that can
    # be the unmatched one in another maximum matching. Removing any of those
    # is exactly equivalent to checking a perfect matching per candidate.
    matched_to = _maximum_matching(future_givers, receivers, forbidden_pairs)
    if len(matched_to) != len(future_givers):
        raise DrawDeadlock("no candidate preserves a complete assignment")
    unmatched = set(receivers) - set(matched_to)
    reverse_edges: dict[int, set[int]] = {receiver: set() for receiver in receivers}
    for matched_receiver, future_giver in matched_to.items():
        for receiver in receivers:
            if allowed(future_giver, receiver, forbidden_pairs):
                reverse_edges[receiver].add(matched_receiver)
    can_be_unmatched = set(unmatched)
    frontier = list(unmatched)
    while frontier:
        receiver = frontier.pop()
        for previous in reverse_edges[receiver]:
            if previous not in can_be_unmatched:
                can_be_unmatched.add(previous)
                frontier.append(previous)
    safe = [receiver for receiver in candidates if receiver in can_be_unmatched]
    if not safe:
        raise DrawDeadlock("no candidate preserves a complete assignment")
    return rng.choice(safe)
