# Định Nghĩa Toán Học MDP — RL Formulation

**Ngày:** 26/09/2026 | **Status:** Mathematical Foundation Complete

## 1. MDP Formulation

$$\text{MDP} = (\mathcal{S}, \mathcal{A}, \mathcal{P}, \mathcal{R}, \gamma)$$

---

## 2. State Space $\mathcal{S}$

**Dimension:** $\dim(\mathcal{S}) = 3M = 117$ (for M=39 advisors)

$$s_t = [\mathbf{c}_t \| \mathbf{r}_t \| \mathbf{l}_t]$$

**Component 1 - Compatibility:** $\mathbf{c}_t \in [0,1]^{39}$
$$c_{t,j} = \text{Cosine Similarity}(\text{student}_t, \text{advisor}_j)$$

**Component 2 - Remaining Capacity:** $\mathbf{r}_t \in [0,1]^{39}$
$$r_{t,j} = \frac{C_j - L_{t,j}}{C_j}$$
where $C_j$ = max quota, $L_{t,j}$ = current load

**Component 3 - Load Ratio:** $\mathbf{l}_t \in [0,1]^{39}$
$$l_{t,j} = \frac{L_{t,j}}{C_j}$$

---

## 3. Action Space $\mathcal{A}$

$$\mathcal{A} = \{0, 1, \ldots, 38\}$$
Action $a_t = j$ means: assign student $t$ to advisor $j$

---

## 4. Transition Dynamics $\mathcal{P}$

When action $a_t = j$ is taken:

$$L_{t+1,j} = L_{t,j} + 1$$

State updates:
- Remaining capacity: $C^{\text{rem}}_{t+1,j} = C_j - L_{t+1,j}$
- Load ratio: $l_{t+1,j} = L_{t+1,j} / C_j$
- Next compatibility: from student $t+1$

**Deterministic:** No randomness in transitions.

---

## 5. Reward Function $\mathcal{R}$

$$r_t = w_c \cdot \text{comp}(t, a_t) + w_f \cdot \Delta\text{Var}_t - w_p \cdot I_{\text{invalid}}$$

**Component 1 - Compatibility Reward:**
$$\text{comp}(t, a_t) \in [0, 1]$$
Direct compatibility score between student and advisor

**Component 2 - Fairness Bonus:**
$$\Delta\text{Var}_t = \text{Var}(\mathbf{L}_t) - \text{Var}(\mathbf{L}_{t+1})$$
Reward if load variance decreases (better balance)

**Component 3 - Violation Penalty:**
$$I_{\text{invalid}}(a_t) = \begin{cases} 1 & \text{if } L_{t,a_t} \geq C_{a_t} \\ 0 & \text{otherwise} \end{cases}$$

**Weights:**
- $w_c = 1.0$ (primary objective)
- $w_f = 0.15$ (fairness objective)
- $w_p = 10.0$ (hard constraint)

---

## 6. Action Masking

Binary mask created before action sampling:

$$m_{t,j} = \begin{cases} 1 & \text{if } L_{t,j} < C_j \\ 0 & \text{if } L_{t,j} \geq C_j \end{cases}$$

In Maskable PPO:
$$\text{logit}'_j = \begin{cases} \text{logit}_j & \text{if } m_{t,j} = 1 \\ -\infty & \text{if } m_{t,j} = 0 \end{cases}$$

Result: $\pi(a = j | s_t) = 0$ for all invalid actions.

**Guarantee:** 100% quota compliance, zero violations.

---

## 7. Discount Factor

$$\gamma = 0.99$$

Long-term strategy over greedy decisions.

---

## 8. Properties

- **Finite Horizon:** Episode ends at $t = N$
- **Deterministic:** No stochasticity in transitions
- **Markovian:** Current state sufficient for optimal action
- **Masked:** Hard constraints enforced structurally

---

**Foundation for Gymnasium environment implementation.**
