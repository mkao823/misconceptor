---
source: notes_recursion
title: "Course notes: Recursion"
course: "C++ data structures"
provenance: "Written for the Misconceptor project on 2026-11-22 in the voice of the course instructor. Original text, not copied from a textbook or the web. Course conventions follow the Mohler ASAG instructor answers; see data/corpus/README.md."
default_concepts: [recursion]
---

# Recursion

## What a recursive function is
<!-- chunk: rec.definition | concepts: recursion, definition, iteration -->

A recursive function is a function that calls itself, either directly or through another function. We use recursion when a problem can be stated in terms of a smaller instance of the same problem. The factorial of n is n times the factorial of n - 1. The number of nodes in a tree is one plus the number of nodes in each of its subtrees. A sorted array can be produced by sorting its two halves and merging them.

```cpp
// n! = n * (n - 1)!, and 1! = 1
long factorial(int n) {
    if (n <= 1)                     // base case
        return 1;
    return n * factorial(n - 1);    // recursive step on a smaller argument
}
```

Every recursive definition has two parts. One part answers the smallest instances directly, with no further call. The other part reduces a larger instance to one or more smaller instances and calls the same function on them.

Anything a recursive function computes could also be computed with a loop: the alternative way to solve a problem that could be solved through recursive functions is iteration. We choose recursion when it follows the shape of the problem or of the data, as it does for trees and for divide-and-conquer algorithms, and a loop when the repetition is a simple count.

## Base case and recursive step
<!-- chunk: rec.base-case-and-step | concepts: recursion, base_case, recursive_step -->

The base case is the instance of the problem that the function can answer directly, without calling itself. For factorial it is n <= 1. For a search in a linked list it is the empty list. For a recursive sort it is an array so small that it needs no further splitting. A function may have more than one base case.

The recursive step, also called the recursion step or the recursive case, does three things. It makes the problem smaller, it calls the function on the smaller problem, and it uses the result of that call to finish the original problem. In factorial the smaller problem is n - 1 and the remaining work is one multiplication.

When you design a recursive function, write down both parts in words before writing any code. What is the smallest input, and what is the answer for it? For any larger input, which smaller input do I call the function on, and what do I do with what comes back?

The base case is usually written as an if statement at the top of the function, but that is a habit and not a rule. The test can be written the other way round, with the recursive call inside the if and nothing at all in the base case, as in a function that prints a list only while the list is not empty. What matters is that at least one path through the function makes no recursive call.

## Convergence: the step must move toward the base case
<!-- chunk: rec.convergence | concepts: recursion, base_case, recursive_step, convergence -->

Having a base case is not enough. Each recursive call must be made on an instance that is closer to a base case than the one before it, so that the chain of calls is certain to arrive there. We say that the recursion converges on the base case. The call factorial(n - 1) converges because the argument decreases by one on every call and must reach 1. A recursive binary search converges because the range between first and last shrinks on every call.

To check convergence, ask two questions about every recursive call. Which quantity measures the size of the problem: the value of n, the length of the array section, the height of the subtree? Does that quantity get strictly smaller on every call, and can it step over the base case without landing on it?

A step of n - 2 with the single base case n == 0 gets smaller every time, but it steps over zero whenever n is odd, so the base case is never reached. A call that passes the same argument again, or a larger one, never gets closer at all.

A base case that cannot be reached is as good as no base case. The test is there in the text of the function, but it never succeeds, and the calls continue.

## Causes of infinite recursion
<!-- chunk: rec.infinite-recursion | concepts: recursion, infinite_recursion, base_case, recursive_step, call_stack -->

Infinite recursion means that the chain of recursive calls never ends. In this course we name two possible causes. Infinite recursion occurs if the recursion step is defined incorrectly, or if the base case is not included.

The base case is not included. The function has no path that returns without calling itself, so every call makes another call.

The recursion step is defined incorrectly. A base case exists, but the calls do not converge on it. The argument is not reduced (factorial(n) calls factorial(n)), or it moves in the wrong direction (n + 1 where n - 1 was meant), or it jumps past the base case (n - 2 when the test is n == 0 and n is odd).

In C++ an infinite recursion does not literally run forever. Every call that has not yet returned keeps a frame on the call stack, so the stack grows with each call until the program runs out of stack memory and is terminated, usually with a stack overflow or a segmentation fault. An infinite loop uses no additional memory per repetition and simply keeps running. The underlying error is the same in both: the test that should end the repetition is missing or can never succeed.

## The call stack: one frame per call
<!-- chunk: rec.call-stack | concepts: recursion, call_stack, stack_frame, local_variables -->

Each call of a function, recursive or not, gets its own activation record, or stack frame, on the program's call stack. The frame holds that call's parameters, its local variables and the place in the caller to return to. When a function calls itself, a new frame is pushed on top of the caller's frame. The caller is not finished. It is suspended, with its own values intact, until the call it made returns.

Because each call has its own frame, each call has its own copy of the parameters and local variables. During factorial(3) there are, at the deepest point, three frames on the stack, with n equal to 3, 2 and 1. Changing n in one frame does not affect the others. A local variable declared inside a recursive function is created again for every call. It is not shared between the calls and it does not accumulate across them. To carry information from one call to the next, pass it as an argument or hand it back as the return value.

The depth of the recursion is the largest number of frames on the stack at one time. Memory use grows with the depth, which is why a very deep recursion can overflow the stack even when it is not infinite.

## What happens after a recursive call returns
<!-- chunk: rec.after-return | concepts: recursion, call_stack, backward_flow, return_value -->

A recursive call is an ordinary function call. When it returns, execution continues in the caller at the point just after the call, with the caller's own parameters and local variables, and the statements that follow the call are then executed.

```cpp
void printUp(int n) {
    if (n == 0) return;     // base case
    printUp(n - 1);         // recursive call
    cout << n << ' ';       // runs after the call above has returned
}
```

The call printUp(3) prints 1 2 3. The calls go all the way down to n == 0 first. The output statements then run in the reverse order of the calls, as the frames are popped one by one. This is called unwinding the recursion. Moving the output statement in front of the recursive call would print 3 2 1 instead.

Reaching the base case therefore does not end the computation. The base case returns to the call that made it, that call finishes its remaining work and returns to its own caller, and so on back to the original call. In factorial every multiplication is performed during the unwinding: factorial(1) returns 1 to factorial(2), which returns 2 to factorial(3), which returns 6.

A function that produces a value must return the result of its recursive call, as in return n * factorial(n - 1). A void function such as printUp just makes the call.

## Iteration and recursion: the similarities
<!-- chunk: rec.iteration-similarities | concepts: recursion, iteration, termination, infinite_recursion -->

Iteration and recursion are two ways of repeating work. In this course we list three similarities between them.

They both involve repetition. Iteration repeats the body of a loop. Recursion repeats the body of a function through repeated function calls.

They both have termination tests. Iteration ends when the loop-continuation condition fails. Recursion ends when a base case is recognized. In both, each repetition is supposed to bring the computation closer to the point where the test succeeds: a loop changes its control variable until the condition fails, and a recursion makes its problem smaller until it reaches the base case.

They can both occur infinitely. A loop whose condition never becomes false is an infinite loop. A recursion whose step does not converge on the base case, or that has no base case, is an infinite recursion.

These are the three similarities expected in this course: repetition, a termination test, and the possibility of running without end.

It is also true that the two are equally powerful. Any problem that can be solved recursively can be solved iteratively, and the reverse, although one of the two is often much clearer than the other.

## Iteration and recursion: the differences
<!-- chunk: rec.iteration-differences | concepts: recursion, iteration, call_stack, overhead -->

The two differ in mechanism and in cost. Iteration uses a repetition statement (for, while, do ... while) and keeps its state in variables that are updated in place. Recursion uses a selection statement, the test for the base case, together with function calls, and keeps its state in the parameters and local variables of each call.

Recursion has an overhead that iteration does not have. Every recursive call pushes a new frame on the call stack. That costs time for the call and memory for the frame, and the memory is held until the call returns. A loop that runs n times uses the same few variables throughout. A recursion that is n calls deep uses n frames. For this reason a simple count or accumulation, such as summing an array or computing a factorial, is normally written as a loop in production code.

Recursion is preferred when it mirrors the problem: processing a tree, where each subtree is a smaller tree, or a divide-and-conquer algorithm such as merge sort, where each half is a smaller array. A recursive solution can always be rewritten with iteration, sometimes with an explicit stack that takes the place of the call stack, so the choice between them is about clarity and cost and not about what can be computed.

## The divide-and-conquer paradigm
<!-- chunk: rec.divide-and-conquer | concepts: recursion, divide_and_conquer, merge_sort -->

Divide and conquer is an algorithm design paradigm with three steps. Divide a problem into smaller subproblems, solve them recursively, and then combine the solutions into a solution for the original problem.

Divide. Split the instance into smaller instances of the same problem, for example the two halves of an array.

Conquer. Solve each smaller instance by a recursive call. An instance small enough to be a base case is solved directly.

Combine. Put the solutions of the subproblems together, for example by merging two sorted halves into one sorted array.

Two things define the paradigm. The subproblems are the same kind of problem as the original, only smaller, which is why the same function can be called on them. And there is a combine step that builds the answer to the original problem out of the answers to the subproblems. Merge sort, quicksort and binary search all follow this pattern. In binary search only one of the two subproblems is kept and the combine step is trivial.

In this course the term means this recursive pattern. Splitting a large program into functions, classes or files, so that each piece is easier to write and to manage, is modular design. It is good practice and is sometimes described with the same words, but its pieces are different tasks and not smaller instances of one problem, and nothing is solved recursively.

## The structure of merge sort
<!-- chunk: rec.merge-sort-structure | concepts: recursion, merge_sort, divide_and_conquer, sorting -->

Merge sort is the standard example of divide and conquer on arrays. It splits the original array into two, sorts each of the two halves, and then merges the sorted arrays.

```cpp
void mergeSort(int a[], int first, int last) {
    if (last - first + 1 <= 1)            // base case: one element
        return;
    int mid = (first + last) / 2;
    mergeSort(a, first, mid);             // sort the left half
    mergeSort(a, mid + 1, last);          // sort the right half
    merge(a, first, mid, last);           // combine the two sorted halves
}
```

The divide step only computes the middle index. The two recursive calls sort the halves. Each of them splits its own half again, so the calls form a tree whose leaves are the base cases. All the comparing of elements happens in merge, which walks through the two sorted halves, repeatedly copies the smaller front element into a temporary array, and finally copies the result back.

The order of events matters. Nothing is merged on the way down. The first merge happens only after the recursion has reached pieces of base-case size and has started to return. The sorted array is built during the unwinding, from small sorted pieces into larger ones, and the last merge, at the top level, produces the fully sorted array.

## The base case of merge sort
<!-- chunk: rec.merge-sort-base-case | concepts: recursion, merge_sort, base_case, sorting -->

The base case for a recursive implementation of merge sort is reached when the size of the array to be sorted is 1 (or 2).

An array of size 1 is already sorted, so the function returns without doing anything. This is the base case used in the code above.

In this course a base case of size 2 is equally acceptable. An array of two elements can be sorted directly, with one comparison and at most one swap, so an implementation may stop there instead of splitting two elements into two arrays of one element each:

```cpp
if (last - first + 1 == 2) {
    if (a[first] > a[last]) swap(a[first], a[last]);
    return;
}
```

An implementation that stops at size 2 still has to stop at size 1 as well, because splitting an array of odd length produces a piece of size 1. So a base case stated as one element, as two elements, or as one or two elements is correct in this course.

The base case is a test on the size of the piece that the current call was given, and it is checked at the start of every call. It is a different thing from the result of the algorithm, the whole array being in order, which is produced by the last merge. It is also a different thing from the running time of the algorithm.
